"""
自定义异常模块
"""


class ContractReviewError(Exception):
    """合同审核基础异常"""
    pass


class InputValidationError(ContractReviewError):
    """输入验证错误"""
    pass


class ProcessingError(ContractReviewError):
    """处理过程错误"""
    pass


class OCRFailedError(ProcessingError):
    """OCR 识别失败"""
    pass


class TranslationError(ProcessingError):
    """翻译失败"""
    pass


class ClauseParsingError(ProcessingError):
    """条款解析失败"""
    pass


class RiskDetectionError(ProcessingError):
    """风险检测失败"""
    pass


class ReportGenerationError(ProcessingError):
    """报告生成失败"""
    pass


class UnsupportedFormatError(InputValidationError):
    """不支持的文件格式"""
    pass


class FileAccessError(InputValidationError):
    """文件访问错误"""
    pass
