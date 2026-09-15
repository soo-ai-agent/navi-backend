# Backend

## Environment

### Python

<a href="https://docs.python.org/release/3.12.0/" target="_blank">
    <img src="https://img.shields.io/badge/Python 3.12-3776AB?
    style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12"/>
</a>

### Web Framework

<a href="https://fastapi.tiangolo.com/" target="_blank">
    <img src="https://img.shields.io/badge/FastAPI-009688?
    style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI-009688"/>
</a>

---

## 1. Install venv, python packages

패키지 설치는 venv 안의 `pip` 하나로만 한다.

``` bash
# in backend directory
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# in venv environment
python -V                       # Python 3.12.x 인지 확인한다
pip install --upgrade pip
pip install -r requirements.txt
```

`python3.12` 가 없다면 먼저 설치한다. 설치 수단은 자유이며(패키지 매니저, pyenv 등), 아래는 시스템 Python 을 건드리지 않는 한 가지 방법이다.

``` bash
# uv 가 없으면: curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
"$(uv python find --system 3.12)" -m venv venv   # 위 python3.12 자리를 대신한다
```

venv 를 다시 만들 때는 `rm -rf venv` 후 위 단계를 반복한다. OS 나 Python 버전이 다른 곳에서 만든 `venv/` 는 재사용할 수 없다.

PyCharm 은 Settings → Python Interpreter → Add Local Interpreter → Select existing 에서 `venv/bin/python` 을 지정한다.

## 2. Configure server environments

- Case 1. write ini file
    ``` bash
    # in backend directory
    nano backend.ini
    ```
    ``` ini
    # Example

    DATA_DIR="/path/to/data"
    ```

- Case 2. Export OS environment variable
    ``` bash
    export DATA_DIR="/path/to/data"
    ```

  환경 변수가 ini 값을 덮어쓴다. `DATABASE_URL` 을 지정하지 않으면 `DATA_DIR` 아래 sqlite(`backend.db`)를 사용한다.

## 3. Run server

``` bash
# in backend directory
# in venv environment
python main.py
```

## 4. Run tests

``` bash
# in backend directory
# in venv environment
python -m unittest discover test
```

타입 오류는 애플리케이션·실행 스크립트·테스트를 함께 검사한다.

```bash
pip install -r requirements-dev.txt
python -m pyright
```

## 5. Collect products and extract conditions

```bash
python -m scripts.sync_disclosure
```

필수 가입조건·우대조건과 근거 원문을 저장한다. 상태와 재시도, 기존 금리 계산과의 연결 범위는
[상품 수집과 조건 추출](docs/product-condition-collection.md)을 참고한다.

---
