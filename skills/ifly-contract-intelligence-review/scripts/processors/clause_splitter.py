"""
条款分段模块
负责合同条款识别、分段、标题提取和主题归类
"""

import re
from typing import List, Dict, Any, Optional

from utils.logger import LoggerMixin


class ClauseSplitter(LoggerMixin):
    """
    条款分段处理器
    将合同文本拆分为结构化的条款
    """

    # 条款标题模式
    CLAUSE_TITLE_PATTERNS = [
        r'^第[一二三四五六七八九十百千0-9]+条',  # 中文编号条款
        r'^第[一二三四五六七八九十百千0-9]+章',  # 章
        r'^\d+\.\d+',  # 数字编号 1.1
        r'^\d+、',  # 顿号编号 1、
        r'^Article\s+\d+',  # 英文条款
        r'^Section\s+\d+',  # 英文章节
        r'^第\s*\d+\s*条',  # 带空格的中文编号
    ]

    # 条款类别关键词
    CLAUSE_CATEGORIES = {
        "definition": ["定义", "释义", "Terms and Definitions", "Definition"],
        "payment": ["付款", "支付", "结算", "Pricing", "Payment", "Payment Terms"],
        "liability": ["违约", "责任", "赔偿", "Liability", "Breach", "Indemnification"],
        "renewal": ["续约", "期限", "终止", "Term", "Renewal", "Termination"],
        "ip": ["知识产权", "版权", "专利", "Intellectual Property", "IP"],
        "confidentiality": ["保密", "机密", "Confidentiality", "Non-disclosure"],
        "dispute": ["争议", "仲裁", "管辖", "Dispute", "Arbitration", "Jurisdiction"],
        "general": ["一般", "通用", "General", "Miscellaneous"],
        "signing": ["签署", "签订", "生效", "Execution", "Effective Date"]
    }

    def __init__(self):
        self.split_result = []

    def extract_title(self, text: str) -> Optional[str]:
        """提取条款标题"""
        for pattern in self.CLAUSE_TITLE_PATTERNS:
            match = re.match(pattern, text.strip())
            if match:
                return match.group(0)
        return None

    def categorize_clause(self, title: str, content: str) -> str:
        """对条款进行分类"""
        if not title:
            # 尝试从内容中识别
            for category, keywords in self.CLAUSE_CATEGORIES.items():
                for keyword in keywords:
                    if keyword in content[:200]:  # 只看前200字符
                        return category
            return "general"

        # 从标题识别
        for category, keywords in self.CLAUSE_CATEGORIES.items():
            for keyword in keywords:
                if keyword in title:
                    return category
        return "general"

    def split_by_markers(self, text: str) -> List[Dict[str, Any]]:
        """基于标记符分割"""
        clauses = []

        # 按行分割
        lines = text.split('\n')
        current_clause = {"title": "", "content": "", "lines": []}
        clause_id = 1

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 检查是否为新条款标题
            is_title = False
            for pattern in self.CLAUSE_TITLE_PATTERNS:
                if re.match(pattern, stripped):
                    is_title = True
                    break

            if is_title:
                # 保存之前的条款
                if current_clause["content"]:
                    clauses.append(self._build_clause(current_clause, clause_id))
                    clause_id += 1

                # 开始新条款
                current_clause = {"title": stripped, "content": "", "lines": []}
            else:
                # 追加到当前条款
                current_clause["lines"].append(stripped)

        # 保存最后一个条款
        if current_clause["content"]:
            clauses.append(self._build_clause(current_clause, clause_id))

        return clauses

    def _build_clause(self, raw_clause: Dict, clause_id: int) -> Dict[str, Any]:
        """构建结构化条款"""
        content = ' '.join(raw_clause["lines"])
        title = raw_clause["title"]
        category = self.categorize_clause(title, content)

        return {
            "id": f"clause_{clause_id}",
            "clause_id": clause_id,
            "title": title,
            "content": content,
            "category": category,
            "char_count": len(content)
        }

    def split(self, text: str) -> List[Dict[str, Any]]:
        """
        条款分段主流程

        Args:
            text: 清洗后的合同文本

        Returns:
            条款列表
        """
        self.logger.info("开始条款分段...")

        # 尝试基于标记符分割
        clauses = self.split_by_markers(text)

        # 如果没有找到任何条款，整个文本作为一条
        if not clauses:
            self.logger.warning("未识别到条款结构，使用全文作为单一条款")
            clauses = [{
                "id": "clause_1",
                "clause_id": 1,
                "title": "",
                "content": text,
                "category": "general",
                "char_count": len(text)
            }]

        self.logger.info(f"条款分段完成，共 {len(clauses)} 个条款")
        self.split_result = clauses
        return clauses

    def get_clause_count(self) -> int:
        """获取条款数量"""
        return len(self.split_result)

    def get_categories(self) -> Dict[str, int]:
        """获取条款类别统计"""
        categories = {}
        for clause in self.split_result:
            cat = clause.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1
        return categories
