class SavingNotFoundError(Exception):
    """요청한 상품 id가 저장된 적금에 없다."""


class SavingBackupError(Exception):
    """상품 갱신 전 DB 백업에 실패했다. 백업 없이는 갱신을 시작하지 않는다."""
