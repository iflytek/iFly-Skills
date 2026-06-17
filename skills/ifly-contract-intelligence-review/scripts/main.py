"""
合同智能审核 Skill 主入口
场景化 workflow skill，负责协调合同审核全流程
"""

import argparse
import sys
import json
import os
from pathlib import Path
from typing import Optional

from config import Config
from errors import ContractReviewError, InputValidationError, ProcessingError
from utils.logger import get_logger
from utils.validation import validate_input_file
from utils.file_utils import ensure_output_dir, load_input_file
from processors.ingest import InputPreprocessor
from processors.text_cleaner import TextCleaner
from processors.clause_splitter import ClauseSplitter
from processors.risk_detector import RiskDetector
from processors.compliance_checker import ComplianceChecker
from processors.bilingual_checker import BilingualChecker
from processors.report_builder import ReportBuilder
from clients.ocr_client import OCRClient
from clients.image_client import ImageClient
from clients.translate_client import TranslateClient
from clients.llm_review_client import LLMReviewClient


logger = get_logger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="合同智能审核 - 对合同进行 OCR 识别、风险检测、合规校对和翻译摘要",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --input contract.pdf
  %(prog)s --input contract.pdf --review-mode deep --focus payment --focus liability
  %(prog)s --input contract.jpg --need-translation --output-format both
  %(prog)s --input contract.docx --lang en --output-format json --save-intermediate
        """
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入文件路径（支持 PDF、图片、Word、Markdown、TXT）"
    )

    parser.add_argument(
        "--input-type",
        choices=["auto", "pdf", "image", "text"],
        default="auto",
        help="输入文件类型（默认 auto 自动检测）"
    )

    parser.add_argument(
        "--lang",
        choices=["zh", "en", "bilingual"],
        default="zh",
        help="合同语言（默认中文）"
    )

    parser.add_argument(
        "--review-mode",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="审核模式：quick=仅高风险项, standard=完整风险+规范, deep=深度分析+翻译摘要"
    )

    parser.add_argument(
        "--focus",
        action="append",
        choices=["payment", "liability", "renewal", "ip", "confidentiality", "dispute"],
        default=[],
        help="重点审查项，可多次指定"
    )

    parser.add_argument(
        "--need-translation",
        action="store_true",
        help="是否需要翻译摘要（英文合同或要求时使用）"
    )

    parser.add_argument(
        "--output-format",
        choices=["markdown", "json", "both"],
        default="markdown",
        help="输出格式"
    )

    parser.add_argument(
        "--output-dir", "-o",
        default="./output",
        help="输出目录（默认 ./output）"
    )

    parser.add_argument(
        "--save-intermediate",
        action="store_true",
        help="是否保存中间处理结果"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )

    return parser.parse_args()


def detect_input_type(file_path: Path) -> str:
    """自动检测输入文件类型"""
    suffix = file_path.suffix.lower()

    if suffix in [".pdf"]:
        return "pdf"
    elif suffix in [".jpg", ".jpeg", ".png", ".bmp", ".heic"]:
        return "image"
    elif suffix in [".docx", ".doc"]:
        return "word"
    elif suffix in [".md", ".txt"]:
        return "text"
    else:
        return "unknown"


def create_abstract_clients():
    """
    创建抽象客户端实例
    注意：这里返回的是抽象接口，实际实现需注入
    """
    config = Config()
    return {
        "ocr": OCRClient(config),
        "image": ImageClient(config),
        "translate": TranslateClient(config),
        "llm_review": LLMReviewClient(config)
    }


def process_pdf_or_image(file_path: Path, clients: dict, config: Config):
    """处理 PDF 扫描件或图片合同"""
    suffix = file_path.suffix.lower()

    # 尝试 OCR 识别
    try:
        if suffix == ".pdf":
            logger.info("执行 OCR 识别...")
            text = clients["ocr"].extract_text(str(file_path))
        else:
            logger.info("执行图片 OCR 识别...")
            text = clients["ocr"].extract_text_from_image(str(file_path))

        if text and len(text.strip()) > 50:
            logger.info(f"OCR 识别完成，文本长度: {len(text)}")
            return text, "ocr"

    except Exception as e:
        logger.warning(f"OCR 识别失败: {e}，尝试图像理解...")

    # OCR 失败时尝试图像理解
    try:
        logger.info("执行图像理解...")
        text = clients["image"].understand_image(str(file_path))
        return text, "image_understanding"
    except Exception as e:
        logger.error(f"图像理解也失败: {e}")
        raise ProcessingError(f"内容提取失败: {e}")


def process_text_file(file_path: Path) -> tuple:
    """处理可编辑文本文件"""
    logger.info("提取文本内容...")
    text = load_input_file(file_path)
    return text, "direct_extract"


def run_review(
    input_path: str,
    input_type: str,
    lang: str,
    review_mode: str,
    focus: list,
    need_translation: bool,
    save_intermediate: bool,
    output_dir: str
) -> dict:
    """
    执行合同审核主流程
    """
    config = Config()
    file_path = Path(input_path)

    # 1. 输入验证
    logger.info(f"验证输入文件: {input_path}")
    validate_input_file(file_path)

    # 2. 自动检测文件类型
    if input_type == "auto":
        input_type = detect_input_type(file_path)
        logger.info(f"自动检测文件类型: {input_type}")

    if input_type == "unknown":
        raise InputValidationError(f"不支持的文件类型: {file_path.suffix}")

    # 3. 创建抽象客户端
    clients = create_abstract_clients()

    # 4. 内容提取
    if input_type in ["pdf", "image"]:
        extracted_text, extraction_method = process_pdf_or_image(file_path, clients, config)
    elif input_type in ["word"]:
        # Word 文件处理（需要安装 python-docx）
        try:
            import docx
            doc = docx.Document(file_path)
            extracted_text = "\n".join([p.text for p in doc.paragraphs])
            extraction_method = "docx_extract"
        except ImportError:
            raise InputValidationError("处理 Word 文件需要安装 python-docx")
    else:
        extracted_text, extraction_method = process_text_file(file_path)

    # 5. 文本清洗
    logger.info("文本清洗...")
    cleaner = TextCleaner()
    cleaned_text = cleaner.clean(extracted_text)

    # 保存中间结果
    if save_intermediate:
        intermediate_dir = Path(output_dir) / "intermediate"
        ensure_output_dir(intermediate_dir)
        (intermediate_dir / "01_cleaned_text.txt").write_text(cleaned_text, encoding="utf-8")

    # 6. 条款分段
    logger.info("条款分段与识别...")
    splitter = ClauseSplitter()
    clauses = splitter.split(cleaned_text)

    if save_intermediate:
        (intermediate_dir / "02_clauses.json").write_text(
            json.dumps(clauses, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # 7. 风险检测
    logger.info("风险检测...")
    detector = RiskDetector()
    risks = detector.detect(clauses, focus, review_mode)

    if save_intermediate:
        (intermediate_dir / "03_risks.json").write_text(
            json.dumps(risks, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # 8. 合规性检查
    logger.info("合规性检查...")
    checker = ComplianceChecker()
    compliance_issues = checker.check(clauses)

    if save_intermediate:
        (intermediate_dir / "04_compliance.json").write_text(
            json.dumps(compliance_issues, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # 9. 双语一致性检查（如果需要）
    bilingual_issues = []
    if lang == "bilingual" or (input_type == "text" and need_translation):
        logger.info("双语一致性检查...")
        bilingual_checker = BilingualChecker()
        bilingual_issues = bilingual_checker.check(clauses)

    # 10. 翻译摘要（如果需要）
    translation_summary = None
    if need_translation or lang == "en":
        logger.info("翻译摘要生成...")
        try:
            translation_summary = clients["translate"].translate_summary(cleaned_text)
        except Exception as e:
            logger.warning(f"翻译失败: {e}")
            translation_summary = None

    # 11. 构建结果
    result = {
        "document_meta": {
            "filename": file_path.name,
            "input_type": input_type,
            "extraction_method": extraction_method,
            "language": lang,
            "review_mode": review_mode,
            "focus": focus if focus else ["all"]
        },
        "extraction_quality": {
            "text_length": len(cleaned_text),
            "confidence": detector.get_confidence(),
            "uncertain_regions": detector.get_uncertain_regions()
        },
        "clauses": clauses,
        "risks": risks,
        "compliance_issues": compliance_issues,
        "bilingual_issues": bilingual_issues,
        "translation_summary": translation_summary,
        "uncertain_items": detector.get_uncertain_items(),
        "human_review_required": detector.get_human_review_flags(),
        "final_summary": ""
    }

    # 生成最终摘要
    result["final_summary"] = ReportBuilder.generate_summary(result)

    # 12. 生成报告
    output_path = Path(output_dir)
    ensure_output_dir(output_path)

    if config.output_format in ["markdown", "both"]:
        logger.info("生成 Markdown 报告...")
        report_builder = ReportBuilder()
        markdown_report = report_builder.build_markdown(result)
        report_file = output_path / f"{file_path.stem}_review_report.md"
        report_file.write_text(markdown_report, encoding="utf-8")
        logger.info(f"报告已保存: {report_file}")

    if config.output_format in ["json", "both"]:
        logger.info("生成 JSON 输出...")
        json_file = output_path / f"{file_path.stem}_review_result.json"
        json_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"JSON 已保存: {json_file}")

    return result


def main():
    """主函数"""
    args = parse_args()

    # 设置日志级别
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"

    try:
        logger.info("=" * 50)
        logger.info("合同智能审核 Skill 启动")
        logger.info("=" * 50)

        # 创建配置
        config = Config()
        config.output_format = args.output_format
        config.output_dir = args.output_dir

        # 执行审核
        result = run_review(
            input_path=args.input,
            input_type=args.input_type,
            lang=args.lang,
            review_mode=args.review_mode,
            focus=args.focus,
            need_translation=args.need_translation,
            save_intermediate=args.save_intermediate,
            output_dir=args.output_dir
        )

        logger.info("=" * 50)
        logger.info(f"审核完成，发现 {len(result['risks'])} 个风险项")
        logger.info(f"合规问题: {len(result['compliance_issues'])} 项")
        if result["human_review_required"]:
            logger.warning(f"需人工复核: {len(result['human_review_required'])} 项")
        logger.info("=" * 50)

        # 打印摘要
        print("\n" + "=" * 50)
        print("审核摘要:")
        print(result["final_summary"])
        print("=" * 50)

        return 0

    except InputValidationError as e:
        logger.error(f"输入验证错误: {e}")
        print(f"\n错误: {e}", file=sys.stderr)
        return 1
    except ContractReviewError as e:
        logger.error(f"审核错误: {e}")
        print(f"\n错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        print(f"\n发生错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
