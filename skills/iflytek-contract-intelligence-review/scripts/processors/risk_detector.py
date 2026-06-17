"""
风险检测模块
负责识别合同中的各类风险点
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from utils.logger import LoggerMixin


@dataclass
class RiskRule:
    """风险检测规则"""
    category: str
    keywords: List[str]
    patterns: List[str]
    default_level: str  # high/medium/low
    description: str
    suggestion: str


@dataclass
class RiskItem:
    """风险项"""
    id: str
    category: str
    level: str  # high/medium/low
    title: str
    description: str
    source: str  # 原文事实/推断/建议
    evidence: str  # 原文片段
    suggestion: str
    clause_id: str = ""


class RiskDetector(LoggerMixin):
    """
    风险检测处理器
    基于规则和模式匹配检测合同风险
    """

    def __init__(self):
        self.rules = self._init_rules()
        self.detected_risks = []
        self.uncertain_regions = []
        self.uncertain_items = []
        self.human_review_flags = []
        self.confidence_score = 1.0

    def _init_rules(self) -> Dict[str, List[RiskRule]]:
        """初始化风险检测规则"""
        rules = {
            "payment": [
                RiskRule(
                    category="payment",
                    keywords=["付款", "支付", "结算", "价款", "费用", "报酬"],
                    patterns=[
                        r"付款.*[前后之间]?",
                        r"支付.*期限",
                        r"结算.*方式",
                        r"逾期.*付款",
                        r"分期.*付款"
                    ],
                    default_level="medium",
                    description="付款相关条款",
                    suggestion="确认付款条件是否明确，包括金额、期限、方式"
                ),
                RiskRule(
                    category="payment",
                    keywords=["验收", "确认", "合格"],
                    patterns=[
                        r"验收.*合格",
                        r"确认.*通过",
                        r"视为.*合格"
                    ],
                    default_level="medium",
                    description="验收条件条款",
                    suggestion="明确验收标准、时限和异议处理方式"
                ),
            ],
            "liability": [
                RiskRule(
                    category="liability",
                    keywords=["违约", "违约金", "赔偿", "补偿"],
                    patterns=[
                        r"违约金.*\d+",
                        r"逾期.*违约金",
                        r"损失.*赔偿",
                        r"双倍.*返还"
                    ],
                    default_level="high",
                    description="违约责任条款",
                    suggestion="审查违约金是否过高，是否存在单向约束"
                ),
                RiskRule(
                    category="liability",
                    keywords=["免责", "不承担", "不负责"],
                    patterns=[
                        r"不承担.*责任",
                        r"免责.*条款",
                        r"不可抗力"
                    ],
                    default_level="medium",
                    description="免责条款",
                    suggestion="审查免责条款是否合理，是否存在免除己方责任"
                ),
            ],
            "renewal": [
                RiskRule(
                    category="renewal",
                    keywords=["续约", "续期", "自动续约", "期满"],
                    patterns=[
                        r"自动续约",
                        r"届满.*续签",
                        r"有效期.*延长"
                    ],
                    default_level="high",
                    description="续约条款",
                    suggestion="确认是否需要书面通知终止，自动续约期限是否明确"
                ),
                RiskRule(
                    category="renewal",
                    keywords=["解除", "终止", "解约"],
                    patterns=[
                        r"单方.*解除",
                        r"提前.*终止",
                        r"解除.*条件"
                    ],
                    default_level="medium",
                    description="解除条件",
                    suggestion="明确解除条件、通知期限和违约责任"
                ),
            ],
            "ip": [
                RiskRule(
                    category="ip",
                    keywords=["知识产权", "版权", "专利", "成果", "归属"],
                    patterns=[
                        r"知识产权.*归",
                        r"著作权.*归",
                        r"专利.*归",
                        r"成果.*归"
                    ],
                    default_level="high",
                    description="知识产权归属",
                    suggestion="明确约定知识产权归属，避免权属纠纷"
                ),
                RiskRule(
                    category="ip",
                    keywords=["授权", "许可", "使用"],
                    patterns=[
                        r"授权.*使用",
                        r"许可.*范围",
                        r"独占.*许可"
                    ],
                    default_level="medium",
                    description="授权许可条款",
                    suggestion="明确授权范围、期限和是否可转让"
                ),
            ],
            "confidentiality": [
                RiskRule(
                    category="confidentiality",
                    keywords=["保密", "机密", "商业秘密"],
                    patterns=[
                        r"保密.*义务",
                        r"商业秘密",
                        r"机密信息"
                    ],
                    default_level="medium",
                    description="保密条款",
                    suggestion="明确保密范围、期限和违约责任"
                ),
                RiskRule(
                    category="confidentiality",
                    keywords=["个人信息", "数据", "隐私"],
                    patterns=[
                        r"个人信息.*保护",
                        r"数据.*安全",
                        r"隐私.*保护"
                    ],
                    default_level="high",
                    description="数据保护条款",
                    suggestion="确认是否符合数据保护法规要求"
                ),
            ],
            "dispute": [
                RiskRule(
                    category="dispute",
                    keywords=["争议", "仲裁", "诉讼", "管辖"],
                    patterns=[
                        r"仲裁.*机构",
                        r"管辖.*法院",
                        r"适用.*法律",
                        r"争议.*解决"
                    ],
                    default_level="medium",
                    description="争议解决条款",
                    suggestion="确认争议解决方式是否明确，管辖地是否合理"
                ),
                RiskRule(
                    category="dispute",
                    keywords=["适用法律", "准据法"],
                    patterns=[
                        r"适用.*法律",
                        r"准据法"
                    ],
                    default_level="medium",
                    description="法律适用条款",
                    suggestion="明确适用法律，跨境合同尤为重要"
                ),
            ]
        }
        return rules

    def detect(
        self,
        clauses: List[Dict[str, Any]],
        focus_areas: List[str],
        review_mode: str
    ) -> List[Dict[str, Any]]:
        """
        风险检测主流程

        Args:
            clauses: 条款列表
            focus_areas: 重点审查领域
            review_mode: 审核模式 quick/standard/deep

        Returns:
            风险列表
        """
        self.logger.info(f"开始风险检测，模式: {review_mode}, 重点: {focus_areas}")

        self.detected_risks = []
        risk_id = 1

        for clause in clauses:
            # 根据审核模式和重点领域筛选
            if review_mode == "quick" and focus_areas:
                # 快速模式只检查重点领域
                if clause.get("category") not in focus_areas:
                    continue

            category = clause.get("category", "general")
            content = clause.get("content", "")
            title = clause.get("title", "")
            clause_id = clause.get("id", "")

            # 检测该条款中的风险
            if category in self.rules:
                for rule in self.rules[category]:
                    risks = self._check_rule(rule, content, title, clause_id, risk_id)
                    self.detected_risks.extend(risks)
                    risk_id += len(risks)

            # 检测不公平格式条款（通用）
            if review_mode != "quick":
                unfair_risks = self._check_unfair_clauses(content, clause_id, risk_id)
                self.detected_risks.extend(unfair_risks)
                risk_id += len(unfair_risks)

        # 过滤低风险项（快速模式）
        if review_mode == "quick":
            self.detected_risks = [
                r for r in self.detected_risks if r["level"] == "high"
            ]

        # 计算整体置信度
        self._calculate_confidence(clauses)

        self.logger.info(f"风险检测完成，共发现 {len(self.detected_risks)} 个风险项")
        return self.detected_risks

    def _check_rule(
        self,
        rule: RiskRule,
        content: str,
        title: str,
        clause_id: str,
        start_id: int
    ) -> List[Dict[str, Any]]:
        """检查单个规则"""
        risks = []
        combined_text = f"{title} {content}"

        # 关键词匹配
        matched_keywords = [
            kw for kw in rule.keywords
            if kw in combined_text
        ]

        if matched_keywords:
            # 提取原文片段作为证据
            evidence = self._extract_evidence(combined_text, matched_keywords[0])

            risk = {
                "id": f"risk_{start_id}",
                "category": rule.category,
                "level": rule.default_level,
                "title": f"{rule.description}（{matched_keywords[0]}）",
                "description": rule.description,
                "source": "推断",  # 风险判断为推断性质
                "evidence": evidence,
                "suggestion": rule.suggestion,
                "clause_id": clause_id
            }
            risks.append(risk)

        return risks

    def _check_unfair_clauses(
        self,
        content: str,
        clause_id: str,
        start_id: int
    ) -> List[Dict[str, Any]]:
        """检查不公平格式条款"""
        risks = []

        unfair_patterns = [
            (r"解释权.*归.*方", "high", "单方解释权", "约定单方解释权可能损害对方利益"),
            (r"不经.*同意.*修改", "high", "单方修改权", "未经同意单方修改合同不公平"),
            (r"放弃.*权利", "medium", "权利放弃", "注意是否包含权利放弃条款"),
            (r"不得.*抗辩", "medium", "禁止抗辩", "禁止抗辩条款可能无效"),
        ]

        for pattern, level, title, desc in unfair_patterns:
            if re.search(pattern, content):
                risks.append({
                    "id": f"risk_{start_id}",
                    "category": "unfair",
                    "level": level,
                    "title": title,
                    "description": desc,
                    "source": "建议",
                    "evidence": content[:200],
                    "suggestion": "建议审查该条款的公平性",
                    "clause_id": clause_id
                })

        return risks

    def _extract_evidence(self, text: str, keyword: str) -> str:
        """提取包含关键词的原文片段"""
        # 找到关键词位置
        pos = text.find(keyword)
        if pos == -1:
            return text[:200]

        # 提取前后各 50 字符
        start = max(0, pos - 50)
        end = min(len(text), pos + 150)

        evidence = text[start:end].strip()
        return evidence

    def _calculate_confidence(self, clauses: List[Dict[str, Any]]):
        """计算检测置信度"""
        if not clauses:
            self.confidence_score = 0.5
            return

        # 基于条款数量和识别情况计算
        clause_count = len(clauses)
        risk_count = len(self.detected_risks)

        # 条款太少或太多都降低置信度
        if clause_count < 3:
            self.confidence_score = 0.6
            self.uncertain_items.append("合同条款数量异常，可能存在识别问题")
        elif clause_count > 100:
            self.confidence_score = 0.7
        else:
            self.confidence_score = 0.85

        # 如果有高风险项未找到原文依据，降低置信度
        high_risks = [r for r in self.detected_risks if r["level"] == "high"]
        if high_risks:
            for risk in high_risks:
                if len(risk.get("evidence", "")) < 10:
                    self.confidence_score = max(0.5, self.confidence_score - 0.1)

    def get_confidence(self) -> float:
        """获取置信度"""
        return self.confidence_score

    def get_uncertain_regions(self) -> List[Dict[str, Any]]:
        """获取识别不确定区域"""
        return self.uncertain_regions

    def get_uncertain_items(self) -> List[str]:
        """获取不确定项列表"""
        return self.uncertain_items

    def get_human_review_flags(self) -> List[str]:
        """获取需人工复核的标志"""
        flags = []

        # 高风险项需要人工复核
        high_risks = [r for r in self.detected_risks if r["level"] == "high"]
        if high_risks:
            flags.append(f"存在 {len(high_risks)} 个高风险项需人工确认")

        # 置信度低于阈值时标记
        if self.confidence_score < 0.7:
            flags.append("识别置信度较低，建议人工复核")

        # 缺少关键条款时标记
        categories = set(c.get("category") for c in self.detected_risks)
        if "payment" not in categories:
            flags.append("未识别到付款条款，可能缺失或识别失败")

        return flags
