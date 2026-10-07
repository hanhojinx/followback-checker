# Followback Checker

**분명 맞팔을 했는데 어느새 나 혼자만 팔로우하고 있는 계정을 찾기가 어렵다면 사용해보세요.**

요즘들어 선팔 걸어놓고 맞팔하자마자 팔로우 끊고 도망가는 계정이 많이 보여 만든 툴입니다. 개인용 오픈소스 CLI로 만들어졌으며 서버, 계정 등록, 웹 UI, 그 외의 잡다한 것들 없이 그냥 터미널로 구동하시면 됩니다.

직접 네트워크 요청을 하는 게 아니라 받아온 export 파일을 읽는 방식이라 좀 번거로운데, 인스타측 정책 때문에 현재는 이 방법이 최선인 것 같습니다. 자동 로그인, 비밀번호 저장, 쿠키 복사등 기능은 보안상 구현하지 않았습니다. 위에 언급했듯 모든 작업은 기본적으로 로컬에서 실행되기 때문에 개인정보 유출 걱정은 안 하셔도 되겠습니다.

## 설치

Python 3.10 이상이 필요합니다. 아래의 모든 커맨드는 레포를 받은 폴더에서 실행하시면 됩니다.

```powershell
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

설치 후 `fbchk` 또는 `python -m followback_checker`로 실행가능합다. 런타임 외부 디펜던시는 없고, 설치 시 pip가 패키지 빌드 툴을 다운로드할 수는 있습니다.

## 데이터 준비

Meta/Instagram의 정보 다운로드 기능으로 **팔로워 및 팔로잉**, **전체 기간**, JSON 또는 HTML 형식의 export를 받으세요. 받아온 zip 파일을 그대로 사용하시거나 압축을 푼 폴더를 지정하시면 됩니다. 계정마다 별도의 export와 `--account` 라벨 사용 권장합니다.

지원되는 파일명 형식:

- `followers.json`, `followers_1.json`, `followers_2.json`, ...
- `following.json`, `following_1.json`, ...
- 위 이름과 동일한 `.html` 확장자 파일

압축파일/폴더 내부의 하위경로도 모두 탐색하며 따로 분리된 followers 파일은 합쳐서 처리합니다. json 파일의 관계배열 및 `relationships_followers`/`relationships_following` wrapper, `string_list_data`, title/href 기반 사용자명 지원합니다. html은 인스타그램 프로필 링크에서 사용자명을 추출합니다. 사용자명은 소문자로 정규화하고 중복을 제거합니다.

두 종류의 파일이 모두 있어야 합니다. 비어있는 json 배열은 유효한 0명 목록이고, 누락되었거나 파싱에 실패한 파일은 에러로 처리됩니다. 파일 하나를 지정하면 같은 폴더에 있는 다른 관계파일도 읽습니다. 입력 파일은 표준 파일명 형식을 유지하셔야 실행됩니다. 아예 다른 계정에서 추출했거나, 같은 계정이더라도 다른 시점에 추출한 데이터를 한 폴더 내부에 섞어두시면 에러가 날 수 있습니다. 압축파일은 디스크에 압축을 풀지 않게 되어있으며 선택된 파일 기준 32 MiB/파일, 128 MiB/전체 제한이 적용됩니다.

## 사용법

```powershell
fbchk scan --source export --path ./instagram-export.zip --account my_username
fbchk scan --source export --path ./instagram-export/ --account my_username
fbchk scan --source export --path ./instagram-export/followers_1.json --account my_username
fbchk nonfollowers --account my_username
fbchk changes --account my_username
fbchk export --format csv --account my_username
```

`scan`은 데이터를 읽고 비교결과를 터미널에 출력한 뒤 스냅샷과 csv/txt/json 파일을 저장합니다. 기타 커맨드는 최근에 저장된 snapshot을 사용하며 인스타그램에서 추가로 데이터를 가져오지 않습니다. 따라서 새 스냅샷이 필요할 때마다 export로 `scan`을 실행하시면 되겠습니다.

`--account`는 인증 없이 기록을 구분하는 **사용자 지정 로컬 라벨**입니다. 생략 시 `local` 라벨을 사용하며, 같은 계정에는 매번 같은 라벨을 사용해야 정상적으로 작동합니다.

저장 위치는 기본적으로 현재 실행 폴더 기준이고, 다음과 같이 변경할 수 있습니다. 공통옵션은 커맨드 앞에 두시든 뒤에 두시든 상관없습니다.

```powershell
fbchk --data-dir ./data --output-dir ./output scan --path ./instagram-export.zip
python -m followback_checker scan --path ./tests/fixtures
```

샘플 fixture는 가상의 사용자명만 포함합니다. 예시는 아래 참고하시면 됩니다.

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

실행했을 때의 결과파일은 기본적으로 `not_following_back_YYYY-MM-DD`으로 저장되며, 동일한 날짜에 1회 이상을 실행하게 되면 `_1`, `_2` 등을 붙여 구분합니다. 스냅샷은 로컬타임, 마이크로세컨드, 고유식별자를 포함하여 같은 시간대에 실행해도 따로따로 저장합니다. 출력날짜는 실행된 디바이스의 시간대 설정을 따릅니다.

## History

매 scan마다 `data/snapshots/YYYY-MM-DD_HHMMSS_ffffff_id.json`을 저장합니다. 이전 기록이 존재한다면 동일한 account 라벨의 직전 스냅샷과 비교합니다.

스냅샷에는 계정별 저장 순번도 기록합니다. 저장 시간이 같거나 PC 시간이 뒤로 조정되어도 이전 실행과 현재 실행의 순서를 유지합니다. 순번이 없는 기존 스냅샷도 계속 읽을 수 있으며, 기존 기록은 시간순으로 정렬한 뒤 새 기록보다 앞에 둡니다.

| 예시 | 예시별 의미 |
| --- | --- |
| `unfollowed_you` | 이전 팔로워에 있었지만 지금은 없는 계정 |
| `new_followers` | 현재 팔로워에 새로 추가된 계정 |
| `you_followed` | 현재 팔로잉에 새로 추가된 계정 |
| `you_unfollowed` | 이전 팔로잉에 있었지만 지금은 없는 계정 |
| `current_non_mutual` | 현재 팔로잉 − 팔로워 |

목록 차이는 내려받은 시점 사이의 변화입니다. 계정 삭제, 사용자명 변경이나 export 누락도 차이로 표기될 수 있으므로 결과로 나왔다고 해서 실제 언팔로우가 확정되는 기록은 아니니 참고용으로만 사용해주시면 되겠습니다. export가 전체 목록인지 파일만으로는 확인이 불가합니다.

## 구조와 확장

```text
src/followback_checker/
  auth.py         브라우저 세션참조용 추상화
  fetcher.py      Fetcher 인터페이스, ExportFetcher, LiveFetcher stub
  parser.py       json/html/zip import
  comparator.py   정규화, 집합 비교, diff (입출력과 관계없음)
  history.py      버전 있는 스냅샷 저장/읽기
  exporter.py     csv/txt/json 결과
  cli.py          argparse 커맨드
tests/fixtures/   가상데이터
data/             로컬 스냅샷 (Git 제외)
output/           결과파일 (Git 제외)
```

미래 fetcher는 `fetch() -> Relationships`만 구현하면 동일한 로직을 사용할 수 있습니다. `auth.py`는 프로필 경로 참조 타입만 정의하되 브라우저나 세션을 읽는 기능은 지원하지 않습니다. 현재 `fbchk scan --source live`는 설명을 출력하고 exit code 1을 반환하며 스냅샷 저장 안합니다. 향후 live 구현도 사용자가 직접 로그인한 기존 브라우저 세션만 고려할 계획이며 자동 로그인이나 비밀번호 저장은 현재로써는 추가할 계획이 없습니다.

## 테스트

```powershell
python -m unittest discover -s tests -v
```

comparator/parser/history 유닛테스트와 CLI 통합테스트를 포함합니다. zip 하위 경로, 분할 목록, html 링크, 비어있거나 잘못된 입력, 계정별 히스토리, 반복출력보존을 검증합니다.

## 로컬 데이터와 Git

`.gitignore`는 `data/`, `output/`, session/cookie/storage_state류, `.env`, 개인 config 및 export zip/관계 파일을 제외합니다. 테스트 fixture만 예외입니다. export는 `data/import/`에 보관하는 것을 권장합니다. 다른 경로나 이름으로 넣은 개인파일은 자동으로 제외되지 않을 수도 있으므로 Git에 올리기 전에 `git status` 한번 확인해주세요. 이미 Git에 추적된 파일에는 `.gitignore`가 적용되지 않습니다.

스냅샷과 그 결과는 암호화되지 않은 로컬 파일입니다. 되도록이면 타인과 공유하지 마시고 본인 PC의 접근권한으로 관리하십시오. 커맨드 실행 중에 같은 출력 디렉토리에 여러 프로세스를 동시에 쓰시는 방식은 지원하지 않습니다. csv나 txt에는 사용자명과 프로필 URL만, 스냅샷에는 라벨, 시간, 팔로워/팔로잉 목록만 저장됩니다.

해당 레포는 MIT License를 사용합니다.
