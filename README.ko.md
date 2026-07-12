# e2e-verification

<p align="center"><strong>에이전트가 조사하고, 결정론적 harness가 실행하며, 검토 가능한 증거를 남깁니다.</strong></p>

<p align="center">
  <a href="README.md">English</a> · <strong>한국어</strong>
</p>

<p align="center"><code>Python 3.11+</code> · <code>API</code> · <code>Playwright</code> · <code>Docker</code> · <code>Apache-2.0</code></p>

`e2e-verification`은 역할, route, API, UI action, 다운로드, 테스트 데이터
lifecycle이 복잡한 애플리케이션을 위한 공개 검증 플랫폼입니다.

에이전트는 무엇을 조사할지 판단하고, 재사용 가능한 skill은 안전한 절차를
정의하며, workflow는 순서·조건·승인·재개를 통제합니다. 실제 제품 접촉과 증거
기록은 결정론적인 harness가 담당합니다.

```text
Agent ──선택──▶ Skill ──사용──▶ Workflow ──실행──▶ Harness
  ▲                                                    │
  └──────── 발견 사항과 후속 조사 제안 ◀───────────────┘
                           │
                           ▼
                  JSON · screenshot · HTML · XLSX
```

플랫폼 core는 framework 중립적입니다. 제품별 역할, selector, endpoint, fixture
지식은 제거 가능한 profile과 명시적으로 로드하는 adapter에만 둡니다.

## 왜 필요한가요?

전통적인 E2E suite는 이미 알고 있는 test case를 반복하는 데 강합니다. 하지만
다음처럼 넓은 검증 질문에는 추가 구조가 필요합니다.

- 각 역할이 의도된 화면과 기능만 보고 접근할 수 있는가?
- 화면에 보이는 control이 예상 route, DOM 상태, API에 실제로 연결되는가?
- 오류 응답이 browser에서 이해 가능하고 복구 가능한 형태로 보이는가?
- export가 구조적으로 유효하면서 보고서에 민감한 row를 노출하지 않는가?
- write fixture가 저장뿐 아니라 완전한 cleanup까지 증명하는가?
- 중단된 실행을 이미 완료된 mutation 없이 안전하게 재개할 수 있는가?

e2e-verification은 이런 질문을 검토 가능한 workflow와 versioned evidence로
바꿉니다.

## 핵심 모델

| 계층 | 책임 | 해서는 안 되는 일 |
|---|---|---|
| **Agent** | 계획, 해석, triage, 정당한 후속 조사 선택 | 실행 범위를 조용히 확대 |
| **Skill** | 재사용 가능한 검증 절차 정의 | 특정 제품의 credential·selector 포함 |
| **Workflow** | 의존성, 조건, 위험, 승인, retry, resume 선언 | profile에서 받은 임의 shell 실행 |
| **Harness** | 결정론적인 API·browser 동작과 증거 생성 | 스스로 다음 조사 항목 결정 |
| **Profile** | 역할, login, route, probe, fixture 계약 기술 | 플랫폼 core 동작 변경 |

## 설치

Python 3.11 이상이 필요합니다. 브라우저 검증이 필요하면 Chromium도
설치합니다.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
python3 -m playwright install chromium
e2e-verify --help
```

Linux CI나 최소 container에서 browser의 OS package까지 설치할 때는 다음을
사용합니다.

```bash
python3 -m playwright install --with-deps chromium
```

Windows PowerShell에서는 다음처럼 실행합니다.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
e2e-verify --help
```

빌드된 wheel을 사용할 수도 있습니다.

```bash
python -m pip install path/to/e2e_verification-0.1.0-py3-none-any.whl
python -m playwright install chromium
```

### 환경별 권장 방식

| 환경 | 권장 설치 | 추가 요구사항 |
|---|---|---|
| Linux, macOS, Windows host | Python 가상환경 | browser probe에는 Chromium 필요 |
| Docker 또는 Compose | 포함된 `Dockerfile`, `compose.yaml` | Compose를 지원하는 Docker Engine |
| API 전용 검증 | Python package | browser 설치 불필요 |
| 폐쇄망 host | 미리 반입한 wheel과 browser bundle | Playwright version과 일치하는 binary |

Python package와 unit matrix는 Linux의 Python 3.11-3.13, macOS와 Windows의
Python 3.12를 대상으로 합니다. 실제 API, Chromium, Docker 통합 검증은 현재
Linux에서 완료됐습니다. ARM64, Alpine/musl, WSL, 사설 CA, proxy 환경은 먼저
`doctor`와 합성 smoke test를 통과시킨 뒤 지원 대상으로 판단해야 합니다.

## 5분 빠른 시작

실제 target에 연결하지 않고 합성 profile과 read-only workflow를 검증합니다.

```bash
e2e-verify validate --config examples/project.example.json
e2e-verify plan --workflow workflows/read-only.json
e2e-verify run --workflow workflows/read-only.json --dry-run
```

실행 환경과 endpoint를 먼저 진단합니다.

```bash
e2e-verify doctor \
  --config examples/project.example.json \
  --target-mode host \
  --connect
```

`doctor`는 다음을 확인합니다.

- OS, Python, container runtime
- API와 web endpoint의 실제 출처
- 필수 credential 환경변수의 존재 여부
- Playwright와 Chromium 사용 가능 여부
- evidence 경로 쓰기 가능 여부
- 선택적으로 DNS와 TCP 연결 가능 여부

credential의 값은 출력하지 않습니다.

## Docker로 바로 확인하기

저장소에는 합성 target과 non-root verifier가 포함돼 있습니다.

```bash
docker compose build
docker compose run --rm verifier
```

합성 계정과 데이터만 사용하며 실제 고객·기관·운영 endpoint에는 연결하지
않습니다. 증거는 Compose가 관리하는 `evidence` volume에 기록됩니다.

| 대상 mode | Verifier 위치 | Target 위치 | 일반적인 hostname |
|---|---|---|---|
| `host` | host | 같은 host | `127.0.0.1` |
| `docker-published` | host | 공개된 container port | `127.0.0.1` |
| `same-network` | container | 같은 Compose/network | `target` 같은 service 이름 |
| `host-from-container` | container | host | 명시적인 host alias |
| `container-local` | container | 같은 container | `127.0.0.1` |
| `external` | 어디서든 | 격리된 원격 target | HTTPS DNS 이름 |
| `auto` | 어디서든 | 알 수 없음 | 진단만 수행하고 모호하면 차단 |

container 안의 `localhost`가 host인지 같은 container인지 임의로 추측하지
않습니다. 모호한 경우 `BLOCKED`로 멈추고 명시적인 mode를 요구합니다. 자세한
내용은 [환경과 target mode](docs/environments.md)를 참고하세요.

## 격리된 테스트 애플리케이션 실행

credential은 profile이 아니라 환경변수로 전달합니다.

```bash
export E2E_ADMIN_ID='test-admin'
export E2E_ADMIN_PASSWORD='...'
export E2E_API_BASE='http://127.0.0.1:8080/api'

e2e-verify run \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

실행이 차단되더라도 이미 완료된 증거는 유지됩니다. 누락된 credential,
browser, endpoint 또는 승인을 보완한 뒤 같은 workflow와 run directory로
재개합니다.

```bash
e2e-verify resume \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

사람이 읽을 수 있는 독립 보고서를 생성합니다.

```bash
e2e-verify report --run-dir evidence/runs/first-run
```

XLSX가 필요하면 optional extra를 설치합니다.

```bash
python -m pip install -e '.[xlsx]'
e2e-verify report \
  --run-dir evidence/runs/first-run \
  --format xlsx
```

run directory에는 전체 `run.json`, step별 `result.json`, redaction된 로그,
선택된 artifact가 저장됩니다. HTML은 기본 사람용 보고서이고 XLSX는 선택적인
profile exporter입니다.

## 안전이 기능 계약의 일부입니다

기본 실행은 read-only입니다. 그 밖의 위험 등급은 workflow가 선언한 이름과
운영자가 제공한 명시적 승인이 모두 필요합니다.

| 위험 등급 | 일반적인 동작 | 기본 정책 |
|---|---|---|
| `read-only` | login, GET probe, route 확인 | 선택된 workflow에서 허용 |
| `download` | CSV·XLSX export | 명시적 승인 필요 |
| `write` | create, update, import commit | 승인과 cleanup 검증 필요 |
| `destructive` | delete, disable, 비가역 상태 전이 | 승인과 cleanup 검증 필요 |
| `external-send` | email, SMS, push, payment, webhook | 별도의 명시적 승인 필요 |

예를 들어 step이 `approval: fixture-write`를 선언했다면 다음 승인 없이는
실행되지 않습니다.

```bash
e2e-verify run \
  --workflow profiles/my-project/workflow.yaml \
  --approve fixture-write
```

mutation step은 cleanup이 독립적으로 검증되지 않으면 `PASS`가 될 수 없습니다.
token, 인증 header, cookie, 알려진 민감 필드, 이메일, 전화번호, 민감한 URL
parameter는 구조화된 증거를 쓰기 전에 redaction됩니다.

> Screenshot과 raw download는 자동으로 완전 비식별화됐다고 간주하지 않습니다.
> 별도 검토가 끝날 때까지 unredacted artifact로 취급하세요.

## 새 프로젝트 profile 만들기

합성 예제를 복사한 뒤 제품별 계약만 작성합니다.

```bash
mkdir -p profiles/my-project
cp examples/project.example.json profiles/my-project/project.json
e2e-verify validate --config profiles/my-project/project.json
```

profile에는 다음 항목을 정의할 수 있습니다.

- login request와 browser selector
- 테스트 계정에 사용할 환경변수 이름
- 역할, home path, menu, 허용·금지 route
- API probe와 예상 status
- browser action과 예상 path, DOM 상태, network binding
- 선택적 adapter를 통한 fixture lifecycle과 cleanup 규칙

다음 substitution을 사용할 수 있습니다.

- `${account.id}`
- `${account.password}`
- `${account.mode}`
- `${role}`
- `${env:NAME}`

실제 password를 profile에 직접 작성하지 마세요.

Spring controller, Django URL configuration, Rails route, 생성된 OpenAPI 같은
framework별 discovery는 profile adapter에 둡니다. profile을 제거할 때
`src/e2e_verification/`을 수정할 필요가 없어야 합니다.

adapter는 실행 가능한 코드이므로 workflow 문서에서 자동 로드하지 않고 CLI가
명시적으로 지정할 때만 로드합니다.

```bash
e2e-verify plan \
  --adapter profiles/my-project/adapter.py \
  --workflow profiles/my-project/workflow.yaml
```

## 재사용 가능한 skills와 agents

저장소에는 검증된 여덟 개 skill이 포함됩니다.

| Skill | 목적 |
|---|---|
| `discover-project` | target 구조와 검증 surface 조사 |
| `verify-rbac-api` | 역할별 API 접근 계약 검증 |
| `verify-browser-routes` | browser route와 menu 검증 |
| `verify-ui-bindings` | UI control과 동작·network binding 검증 |
| `verify-error-ux` | 오류 상태와 복구 UX 검증 |
| `verify-exports` | download와 export 구조 검증 |
| `verify-safe-writes` | 승인된 mutation과 cleanup 검증 |
| `closeout-evidence` | 증거 완전성, redaction, 종료 조건 검토 |

`agents/`의 역할 정의가 이 skill들을 조합합니다.

- `verification-lead`: 가장 작은 안전한 workflow를 계획하고 조정합니다.
- `failure-triage`: 실패를 분류하고 최소 재현 경로를 제안합니다.
- `evidence-reviewer`: 증거, redaction, cleanup, 공개 가능성을 검토합니다.

설치된 schema, agent, skill, 예제의 위치는 다음 명령으로 찾을 수 있습니다.

```bash
e2e-verify assets
```

## 상태와 종료 코드

| 상태 | 의미 |
|---|---|
| `PASS` | 설정된 관찰 가능 계약을 증명함 |
| `FAIL` | 실제 동작이 계약과 다름 |
| `REVIEW` | 증거는 있으나 사람 또는 제품 정책 판단이 필요함 |
| `BLOCKED` | credential, fixture, 환경, browser, 승인이 부족함 |
| `SKIP` | workflow 조건이 step을 선택하지 않음 |

증거가 없다는 사실을 성공으로 바꾸지 않습니다.

| 종료 코드 | 의미 |
|---|---|
| `0` | 실행 완료 또는 review 가능한 결과 |
| `2` | 실패 또는 잘못된 invocation |
| `3` | 안전하게 차단된 workflow |

## 직접 실행 명령

workflow 외에도 같은 profile과 evidence 계약을 사용하는 직접 명령을 제공합니다.

```bash
e2e-verify api --config profiles/my-project/project.json
e2e-verify browser --config profiles/my-project/project.json
e2e-verify all --config profiles/my-project/project.json
```

직접 명령은 read-only probe만 허용합니다. write, destructive,
external-send 동작은 이름 있는 승인과 cleanup이 선언된 workflow를 사용해야
합니다.

## 저장소 구조

```text
agents/                    이식 가능한 검증 역할
skills/                    재사용 절차와 UI metadata
workflows/                 선언형 실행 graph
schemas/                   workflow, agent, run, step 계약
src/e2e_verification/
  config.py                profile 검증과 substitution
  environment.py           runtime, endpoint, preflight 진단
  api_harness.py           결정론적인 API probe
  browser_harness.py       결정론적인 browser probe
  workflow.py              계획, gate, retry, resume
  evidence.py              상태와 증거 model
  redaction.py             저장 시점 redaction
  reporting.py             사람이 읽는 보고서
profiles/<project>/        제거 가능한 private 제품 adapter와 reference
examples/synthetic-target/ 공개용 합성 target
tests/                     계약과 실행 테스트
```

공개 저장소에는 제품 중립적인 플랫폼 코드와 합성 예제만 포함합니다.
`tools/public_repo_gate.py`는 공개 후보의 민감정보, 절대 사용자 경로, 생성 증거,
Git 이력을 검사합니다.

## 개발과 release 검증

```bash
python -m pip install -e '.[dev]'
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests tools
python3 tools/release_check.py
python3 tools/public_repo_gate.py
```

배포 archive도 별도로 검사합니다.

```bash
python -m build
python3 tools/check_artifact.py dist/*
python3 tools/generate_sbom.py dist/sbom.cdx.json
```

관련 문서:

- [Architecture](docs/architecture.md)
- [환경과 target mode](docs/environments.md)
- [오픈소스 경계](docs/open-source-boundary.md)
- [보안 정책](SECURITY.md)
- [기여 가이드](CONTRIBUTING.md)
- [공개 정책](PUBLICATION_POLICY.md)
- [Release 절차](docs/release.md)
- [의존성 정책](docs/dependency-policy.md)
- [보안 감사 기록](docs/security-audit.md)
- [오픈소스 준비 상태](docs/readiness.md)
- [Roadmap](ROADMAP.md)

## 라이선스

Apache License 2.0. 자세한 내용은 [LICENSE](LICENSE)를 참고하세요.
