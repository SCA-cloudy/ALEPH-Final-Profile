# 계속 새로 쓰는 장치

변준혁의 소개 사이트(`docs/`)를 새 기록으로 다시 만드는 장치(`run.py`)입니다. AI를 부르지 않고 API 키도 필요 없으며, Python 3 표준 라이브러리만 씁니다.

## 돌리는 방법 세 단계

1. `input/`에 `ritual.json`(리추얼 기록 JSON), `attendance.csv`(내 출석 기록), `assignments.csv`(내 제출 현황)를 넣습니다.
2. 이 폴더에서 `python run.py`를 실행합니다. (`python`이 안 되면 `python3`)
3. `output/candidates.md`에서 쓰고 싶은 문장의 id를 `content/approved.json`에 넣고 다시 실행합니다. 승인한 문장만 `docs/index.html`에 들어갑니다.

같은 입력에 같은 결과가 나오는지는 `python run.py --verify`로 확인합니다. 임시 폴더에서 두 번 만들어 `output/compare_two_runs.txt`에 비교 결과를 적습니다.

## 폴더

| 위치 | 내용 |
|---|---|
| `input/` | 입력 기록. 공개 저장소에는 올리지 않고 제출 ZIP에만 넣습니다 |
| `content/` | 페이지 틀과 승인 목록 |
| `output/` | 마지막 결과: 숫자, 문단 후보, 두 번 실행 비교 |
| `docs/` | 공개 사이트: 페이지, 논문 PDF, 지원 서류 |

## 입력 형식

- `attendance.csv`: `date,status,confirmed` (status는 출석·지각·결석, confirmed는 확정·미확정)
- `assignments.csv`: `id,title,submitted,status`
- `ritual.json`: 플랫폼에서 받은 형식 그대로. 넣기 전에 다른 사람의 이름은 직접 지웁니다.
