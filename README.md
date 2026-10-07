# Followback Checker

**A privacy-first, local Instagram follow relationship analyzer.**

Instagram에서 받은 팔로워·팔로잉 데이터를 비교해 **내가 팔로우하지만 나를 팔로우하지 않는 계정**을 찾는 개인용 오픈소스 CLI입니다. 서버, 계정 등록, 웹 UI 없이 자신의 PC에서 실행합니다.

- This tool does not collect or transmit Instagram credentials.
- All account data is processed locally.
- This is an unofficial tool and may break if Instagram changes its behavior.
- Third-party/unofficial access may be rate-limited or restricted; export-based parsing is the stable path.

현재 버전은 네트워크 요청을 하지 않으며 export 파일만 읽습니다. `live` 소스는 분리된 미구현 stub입니다. 자동 로그인, 비밀번호 저장, 쿠키 복사 기능은 없습니다.

## 설치

Python 3.10 이상이 필요합니다. 아래 명령은 레포를 내려받은 폴더에서 실행합니다.

```powershell
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

설치 후 `fbchk` 또는 `python -m followback_checker`로 실행할 수 있습니다. 런타임 외부 의존성은 없습니다. 설치 시에는 pip가 패키지 빌드 도구를 다운로드할 수 있습니다.

## 데이터 준비

Meta/Instagram의 정보 다운로드 기능으로 **팔로워 및 팔로잉**, **전체 기간**, JSON 또는 HTML 형식의 export를 받으세요. ZIP을 그대로 사용하거나 압축을 푼 폴더를 지정합니다. 계정마다 별도의 export와 `--account` 라벨을 사용하세요.

지원 파일 이름:

- `followers.json`, `followers_1.json`, `followers_2.json`, ...
- `following.json`, `following_1.json`, ...
- 위 이름의 `.html` 파일

폴더/ZIP 안의 하위 경로도 검색하며 분할된 followers 파일은 합칩니다. JSON의 관계 배열 및 `relationships_followers`/`relationships_following` wrapper, `string_list_data`, title/href 기반 사용자명을 지원합니다. HTML은 Instagram 프로필 링크에서 사용자명을 추출합니다. 사용자명은 소문자로 정규화하고 중복을 제거합니다.

두 종류의 파일이 모두 있어야 합니다. 빈 JSON 배열은 유효한 0명 목록이고, 누락되거나 파싱에 실패한 파일은 오류로 처리합니다. 파일 하나를 지정하면 **같은 폴더에 있는 다른 관계 파일도 읽습니다**. 입력 파일은 표준 이름을 유지하세요. 서로 다른 계정이나 시점의 export를 한 폴더/ZIP에 섞지 마세요. ZIP은 디스크에 압축 해제하지 않으며 선택한 파일 기준 32 MiB/파일, 128 MiB/전체 제한을 적용합니다.

## 사용법

```powershell
fbchk scan --source export --path ./instagram-export.zip --account my_username
fbchk scan --source export --path ./instagram-export/ --account my_username
fbchk scan --source export --path ./instagram-export/followers_1.json --account my_username
fbchk nonfollowers --account my_username
fbchk changes --account my_username
fbchk export --format csv --account my_username
```

`scan`은 데이터를 읽고, 비교 결과를 터미널에 출력한 뒤 snapshot과 CSV/TXT/JSON을 저장합니다. 나머지 명령은 가장 최근에 저장된 snapshot을 사용하며 Instagram에서 새 데이터를 가져오지 않습니다. 최신 상태가 필요할 때 새 export로 `scan`을 실행하세요.

`--account`는 인증 없이 기록을 구분하는 **사용자 지정 로컬 라벨**입니다. 파일 소유 계정을 자동 검증하지 않습니다. 생략 시 `local` 라벨을 사용하며, 같은 계정에는 매번 같은 라벨을 사용해야 합니다.

저장 위치는 현재 실행 폴더 기준입니다. 다음과 같이 변경할 수 있습니다. 공통 옵션은 명령 앞이나 뒤에 둘 수 있습니다.

```powershell
fbchk --data-dir ./data --output-dir ./output scan --path ./instagram-export.zip
python -m followback_checker scan --path ./tests/fixtures
```

샘플 fixture는 가상의 사용자명만 포함합니다. 예상 출력:

```text
Account label: @local
Followers: 2
Following: 3
Mutual: 1
Not following back: 2
@carol
@dave
Snapshot: data/snapshots/2026-10-06_143000_123456_a1b2c3d4.json
Saved: output/not_following_back_2026-10-06.csv
Saved: output/not_following_back_2026-10-06.txt
Saved: output/not_following_back_2026-10-06.json
No previous snapshot; changes will be available after the next scan.
```

첫 실행의 결과 파일은 `not_following_back_YYYY-MM-DD`이며, 같은 날 후속 실행은 `_1`, `_2` 등을 붙여 기존 파일을 보존합니다. Snapshot은 로컬 시간·마이크로초·고유 식별자를 포함해 같은 초에 실행해도 각각 저장합니다. 출력 날짜는 실행 PC의 시간대를 따릅니다.

## History

매 scan마다 `data/snapshots/YYYY-MM-DD_HHMMSS_ffffff_id.json`을 저장합니다. 이전 기록이 있으면 같은 account 라벨의 직전 snapshot과 비교합니다.

| 항목 | 의미 |
| --- | --- |
| `unfollowed_you` | 이전 followers에 있었지만 현재 없는 계정 |
| `new_followers` | 현재 followers에 새로 나타난 계정 |
| `you_followed` | 현재 following에 새로 나타난 계정 |
| `you_unfollowed` | 이전 following에 있었지만 현재 없는 계정 |
| `current_non_mutual` | 현재 following − followers |

목록 차이는 내려받은 두 시점의 변화입니다. 계정 삭제·사용자명 변경·export 누락도 차이로 나타날 수 있으므로 실제 언팔로우 행동을 확정하는 기록은 아닙니다. Export가 전체 목록인지 파일만으로 확인할 수는 없습니다.

## 구조와 확장

```text
src/followback_checker/
  auth.py         브라우저 세션 참조용 추상화
  fetcher.py      Fetcher 인터페이스, ExportFetcher, LiveFetcher stub
  parser.py       JSON/HTML/ZIP import
  comparator.py   정규화·집합 비교·diff (입출력과 독립)
  history.py      버전 있는 snapshot 저장/읽기
  exporter.py     CSV/TXT/JSON 결과
  cli.py          argparse 명령
tests/fixtures/   가상 데이터
data/             로컬 snapshot (Git 제외)
output/           결과 파일 (Git 제외)
```

미래 fetcher는 `fetch() -> Relationships`만 구현하면 동일한 비교·저장 로직을 사용할 수 있습니다. `auth.py`는 프로필 경로 참조 타입만 정의하며 브라우저/세션을 읽지 않습니다. 현재 `fbchk scan --source live`는 설명을 출력하고 종료 코드 1을 반환하며 snapshot을 저장하지 않습니다. 향후 live 구현도 사용자가 직접 로그인한 기존 브라우저 세션만 고려하며 자동 로그인·비밀번호 저장은 지원하지 않습니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

Comparator/parser/history 단위 테스트와 CLI 통합 테스트를 포함합니다. ZIP 하위 경로, 분할 목록, HTML 링크, 빈/잘못된 입력, 계정별 history, 반복 출력 보존을 검증합니다.

## 로컬 데이터와 Git

`.gitignore`는 `data/`, `output/`, session/cookie/storage_state류, `.env`, 개인 config 및 export ZIP/관계 파일을 제외합니다. 테스트 fixture만 예외입니다. export는 `data/import/`에 보관하는 것을 권장합니다. 다른 경로나 이름으로 넣은 개인 파일은 자동 제외되지 않을 수 있으므로 Git에 올리기 전 `git status`를 확인하세요. 이미 Git에 추적된 파일에는 `.gitignore`가 적용되지 않습니다.

Snapshot과 결과는 **암호화되지 않은 로컬 파일**입니다. 다른 사람과 공유하지 않고 본인 PC의 접근 권한으로 관리하세요. 명령 실행 중 같은 출력 폴더에 여러 프로세스를 동시에 쓰는 사용 방식은 지원하지 않습니다. CSV/TXT에는 사용자명과 프로필 URL만, snapshot에는 라벨·시간·팔로워/팔로잉 목록만 저장합니다.

License: MIT.
