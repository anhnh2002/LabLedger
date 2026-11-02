# LabLedger — Product and Technical Specification

**Phiên bản tài liệu:** 0.1.0  
**Ngày cập nhật:** 2026-11-02  
**Trạng thái:** Spec triển khai; các kiểm chứng host thực tế được ghi riêng trong docs/VALIDATION.md.  
**Ngôn ngữ:** Tiếng Việt; templates và agent instructions dùng tiếng Anh để tái sử dụng giữa các coding agents.  
**Nền tảng mục tiêu:** Codex và Claude Code, ưu tiên môi trường local có quyền truy cập repository.

## 1. Tổng quan

LabLedger là plugin hỗ trợ researcher làm việc với coding agents qua nhiều session. Plugin chuẩn hóa việc khởi tạo dự án, thảo luận quyết định nghiên cứu, bàn giao context, theo dõi thí nghiệm và tích lũy findings có bằng chứng.

Tên **LabLedger** thể hiện vai trò một sổ nghiên cứu dùng chung giữa researcher và agent. Tên định danh plugin là `labledger`; mọi cách sử dụng diễn ra trong session Codex hoặc Claude Code, không có CLI riêng. Đây là tên sản phẩm đề xuất, không phải xác nhận về quyền sở hữu tên hoặc tính khả dụng trên registry.

Mô tả ngắn:

> LabLedger helps researchers and coding agents discuss decisions, implement general solutions, run traceable experiments, and retain evidence across sessions.

Workflow chủ đạo đã thống nhất:

> Brainstorm trong session hiện tại → lưu tài liệu Markdown → hướng dẫn user mở **session mới** trong cùng repository → bật **native Plan Mode** → đọc tài liệu bàn giao → lập và duyệt kế hoạch → chuyển sang thực thi → triển khai, thử nghiệm và lưu findings.

LabLedger không xây dựng một planning engine hoặc implementation engine riêng. Plugin chuẩn bị context và duy trì convention, records và evidence trong khi Codex hoặc Claude Code thực hiện planning và implementation bằng khả năng có sẵn.

## 2. Bài toán và mục tiêu

### 2.1. Các vấn đề cần giải quyết

- Agent thường sửa được case đang quan sát nhưng chưa xử lý lớp nguyên nhân tổng quát.
- Các quyết định về phương pháp có thể được thực hiện trước khi researcher hiểu các lựa chọn và đánh đổi.
- Lịch sử thử nghiệm bị phân tán trong chat, terminal và file output không rõ nguồn gốc.
- Kết quả âm, lỗi hạ tầng và hướng đã thất bại dễ bị bỏ quên.
- Session mới thiếu context và có thể lặp lại các thử nghiệm cũ hoặc thay đổi quyết định đã thống nhất.
- Kết quả chạy thành công dễ bị nhầm với kết quả nghiên cứu tích cực.
- Việc liên tục quan sát evaluation feedback có thể ảnh hưởng tới tính độc lập của kết luận.

### 2.2. Mục tiêu

1. Khởi tạo cấu trúc nghiên cứu nhất quán, thích ứng với repository hiện có.
2. Thảo luận rõ với user trước khi chốt quyết định nghiên cứu.
3. Bàn giao đủ context để một session mới bắt đầu native planning mà không phụ thuộc chat cũ.
4. Khuyến khích implementation tổng quát trong phạm vi được tuyên bố.
5. Theo dõi các lần thử, kể cả thất bại, bị hủy hoặc không đủ bằng chứng.
6. Liên kết quyết định, thí nghiệm, run, finding và claim.
7. Truy hồi findings trước khi lặp lại một hướng nghiên cứu.
8. Dùng chung records giữa Codex và Claude Code.

### 2.3. Ngoài phạm vi MVP

- Thay thế native Plan Mode hoặc tự động điều khiển UI để chuyển mode.
- Tự mở session mới rồi coi context đã được bàn giao thành công.
- Tự quyết định research direction thay user.
- Chứng minh một giải pháp đúng cho mọi đầu vào hoặc chắc chắn không overfit.
- Theo dõi tuyệt đối mọi command ở mọi terminal.
- Cung cấp distributed scheduler, dashboard, vector database hoặc multi-agent orchestration.
- Chống giả mạo records bởi một actor có toàn quyền ghi vào cùng filesystem.
- Bảo đảm tái lập tuyệt đối các API model có yếu tố bất định hoặc backend thay đổi.

## 3. Nguyên tắc vận hành

| Nguyên tắc | Hành vi bắt buộc |
| --- | --- |
| Discuss before deciding | Trình bày evidence, lựa chọn và đánh đổi trước khi chốt quyết định nghiên cứu. |
| Generalize within scope | Nêu phạm vi, giả định và cơ chế giải quyết một lớp vấn đề. |
| Preserve evaluation integrity | Ghi rõ vai trò dữ liệu, exposure và protocol thay đổi. |
| Record every attempt | Giữ lại kết quả tích cực, tiêu cực, không rõ ràng và execution failures. |
| Evidence before claims | Liên kết kết luận với run, artifact, nguồn hoặc derivation cụ thể. |
| Recall before repeating | Tìm findings liên quan và giải thích điều gì mới trước khi thử lại. |
| Preserve history | Đính chính bằng records mới; không âm thầm viết lại lịch sử. |
| Continue across sessions | Context quan trọng phải tồn tại trong tài liệu và records của repo. |
| Prefer proportionate solutions | Ưu tiên giải pháp nhỏ xử lý đúng nguyên nhân; không bắt mọi fix thành framework. |

### 3.1. Giới hạn của enforcement

Phân biệt ba mức:

1. **Instruction:** conventions trong `AGENTS.md`, `CLAUDE.md` và skills hướng dẫn hành vi agent.
2. **Deterministic checks:** Backend đi kèm plugin kiểm tra schema, references, trạng thái, metadata và scope đã ghi nhận.
3. **Host integration:** hooks nhắc hoặc chặn một số thao tác khi runtime hỗ trợ và user đã cấu hình.

Backend có thể từ chối chạy một experiment thiếu protocol đã duyệt, nhưng không thể ngăn một actor chạy cùng script trực tiếp ngoài plugin. Một trường `approved_by` trong file không tự chứng minh người duyệt là user. MVP cần ghi bằng chứng phê duyệt một cách trung thực và nêu rõ trust model; không quảng bá workflow như một security boundary.

## 4. Kiến trúc

### 4.1. Ba lớp

| Lớp | Trách nhiệm |
| --- | --- |
| Research core | Domain models, schemas, state transitions, records, runner, search, validation. |
| Shared workflows | Init, brainstorm, handoff, recall, analyze, resume, report, generalization review. |
| Host adapters | Skill wrappers, instruction integration, package metadata và optional hooks riêng từng host. |

Shared workflows là nguồn nội dung duy nhất. Adapter sinh wrappers phù hợp cho từng host; không duy trì hai bản hướng dẫn thủ công dễ lệch nhau.

### 4.2. Công nghệ đề xuất

| Thành phần | Lựa chọn MVP |
| --- | --- |
| Core | Python 3.11+ backend nội bộ, đóng gói cùng plugin. |
| Machine-readable records | JSON, có `schema_version`. |
| Human-readable documents | Markdown. |
| Configuration | TOML. |
| Validation | JSON Schema hoặc typed models; chọn một schema authority. |
| Process execution | `subprocess`, argv list; không tự nội suy shell. |
| Search | Metadata filtering và full-text search; SQLite FTS là tùy chọn. |
| Persistence | Filesystem; Git cho metadata và tài liệu. |
| LLM | Coding agent hiện tại; core không cần API key trong MVP. |
| Index | Derived data, có thể rebuild từ canonical records. |

Không suy diễn research outcome hoặc confidence chỉ từ exit code. Các bước diễn giải do agent/user thực hiện, có evidence và giới hạn rõ ràng.

### 4.3. Đóng gói

Một source repository chứa core, workflows, templates, adapter generators và tests. Build tạo hai package outputs:

| Output | Thành phần |
| --- | --- |
| Codex package | Root `plugin.json` theo định dạng portable phù hợp tài liệu host; `skills/`; core/helpers và resources cần thiết. |
| Claude Code package | `.claude-plugin/plugin.json`; `skills/`; core/helpers và resources cần thiết. |

Không cung cấp executable LabLedger hoặc bước cài core riêng. Agent tự tạo JSON requests từ hội thoại và gọi helper nội bộ theo protocol đi kèm. Helper chuẩn bị dependencies đã pin trong cache riêng; cần Python 3.11+ và kết nối package index lần đầu. Không sửa dependencies của repository nghiên cứu.

Adapter có thể dùng compatibility manifest nếu phiên bản host yêu cầu. Mọi path trong package phải resolve từ package root và không phụ thuộc đường dẫn máy developer.

Định dạng package, cách discovery và hooks phải được kiểm tra trên phiên bản host mục tiêu trước release. Không coi hỗ trợ skills là đồng nghĩa với hỗ trợ đầy đủ lifecycle hooks.

## 5. Cấu trúc dự án được khởi tạo

### 5.1. Các đường dẫn chuẩn

| Đường dẫn | Vai trò |
| --- | --- |
| `research/CHARTER.md` | Mục tiêu, phạm vi, nguyên tắc và ngân sách. |
| `research/STATUS.md` | Entry point tổng quan dự án; liên kết task đang hoạt động. |
| `research/tasks/<task-id>/BRIEF.md` | Kết quả brainstorm và hướng đã thống nhất. |
| `research/tasks/<task-id>/HANDOFF.md` | Entry point cho session mới. |
| `research/tasks/<task-id>/PLAN.md` | Bản kế hoạch đã duyệt, persist lúc vào execution. |
| `research/tasks/<task-id>/STATUS.md` | Tiến độ và bước tiếp của task. |
| `research/decisions/<decision-id>/record.json` | Canonical decision record. |
| `research/experiments/<experiment-id>/record.json` | Canonical experiment record. |
| `research/findings/<finding-id>/record.json` | Canonical finding record. |
| `research/findings/<finding-id>/NOTE.md` | Phân tích dài hoặc ví dụ khi cần. |
| `research/claims/<claim-id>/record.json` | Claim, scope và evidence references. |
| `research/references/` | Ghi chú tài liệu và nguồn. |
| `research/reports/` | Báo cáo tổng hợp có dẫn chứng. |
| `artifacts/runs/<run-id>/` | Manifest, logs, metrics và output của một run. |
| `.labledger/config.toml` | Cấu hình dự án. |
| `.labledger/schemas/` | Schema theo phiên bản nếu cần bundle vào repo. |
| `.labledger/cache/` | Derived index/cache có thể xóa và rebuild. |
| `AGENTS.md` | Entry instructions cho Codex. |
| `CLAUDE.md` | Entry instructions cho Claude Code. |

Records JSON là nguồn dữ liệu có cấu trúc. Markdown không sao chép thủ công toàn bộ fields của record; dùng ID/reference và giải thích thêm. Nếu sinh human-readable view từ JSON, đánh dấu view là generated.

Thư mục source, tests, scripts và configs của nghiên cứu chỉ được tạo khi cần; không tái cấu trúc repository hiện có theo một skeleton cứng.

### 5.2. Git và artifacts

- Commit charter, task documents, metadata records, findings và cấu hình không chứa secrets.
- Logs lớn, model outputs lớn, datasets và cache mặc định nằm ngoài Git.
- Nếu artifact ở external storage, lưu URI, checksum, size và yêu cầu truy cập; không lưu signed URL hết hạn làm reference lâu dài.
- Giữ run manifest cục bộ hoặc bản export metadata lâu dài kể cả khi raw artifacts ở nơi khác.
- Không tự xóa artifacts thất bại; retention do user cấu hình và mọi thao tác xóa cần giữ tombstone/metadata cần thiết.

## 6. Khởi tạo với init

### 6.1. Entry points

| Host | Entry point đề xuất |
| --- | --- |
| Claude Code | `/labledger:init` |
| Codex | `$labledger-init` |

Không ghi đè `/init` native trong MVP. Các command trên là thành phần sẽ được tạo bởi LabLedger, không phải lệnh đã tồn tại khi chưa cài plugin.

### 6.2. Quy trình

1. Resolve project root; đọc instructions và cấu trúc hiện tại.
2. Nhận diện ngôn ngữ, môi trường, build/test entry points và cấu trúc nghiên cứu có sẵn.
3. Trình bày thông tin đã xác nhận; các thông tin thiếu phải là `unknown` hoặc câu hỏi, không tự bịa.
4. Thống nhất research charter với user.
5. Hiển thị kế hoạch tạo/bổ sung file và xung đột cần xử lý.
6. Tạo scaffold theo charter.
7. Chạy `doctor` để kiểm tra cấu trúc và báo bước tiếp theo.

Agent thực hiện hội thoại ngay trong session, tự tạo JSON theo nội dung đã thống nhất, dry-run rồi gọi backend đi kèm plugin để khởi tạo. User không tạo JSON hoặc gọi backend bằng tay. Backend xử lý thao tác xác định, không gọi LLM riêng. Khi đang ở native Plan Mode, chỉ khảo sát/thảo luận và chờ execution mới ghi file.

### 6.3. Research charter

Charter tối thiểu phải nêu:

- Research questions và động lực.
- Phạm vi, giả định, non-goals.
- Baseline và tiêu chí thành công.
- Vai trò datasets/splits và nguồn dữ liệu.
- Ngân sách thời gian, compute/API và điều kiện dừng.
- Chính sách phê duyệt quyết định.
- Phạm vi thao tác agent được tự thực hiện sau khi đã thống nhất.
- Entry points cho build, tests và experiments đã biết.

### 6.4. Yêu cầu idempotency

- Backend `init` với `dry_run: true` không sửa file.
- Chạy lại init không tạo trùng section, record hoặc thư mục tương đương.
- Chỉ cập nhật vùng instructions có markers do LabLedger quản lý.
- Khi user sửa vùng managed, hiển thị conflict/diff thay vì ghi đè.
- Không thay toàn bộ `AGENTS.md` hoặc `CLAUDE.md`.
- Không tự di chuyển code/dataset hoặc tạo commit.

## 7. Brainstorm và quyết định nghiên cứu

### 7.1. Khi nào phải thảo luận

Mọi quyết định ảnh hưởng tới phương pháp, phạm vi nghiên cứu, evaluation hoặc diễn giải kết quả phải được thảo luận trước khi chốt. Ví dụ:

- Chọn architecture, algorithm, prompt hoặc retry policy.
- Chọn baseline, metric, dataset hoặc cách loại mẫu.
- Chọn cách sửa lỗi có nhiều nguyên nhân/phương án đáng cân nhắc.
- Thay đổi protocol hoặc ngân sách đã thống nhất.
- Quyết định tiếp tục, tạm dừng hoặc từ bỏ một hypothesis.
- Chuyển một observation thành claim rộng hơn.

Thao tác thực thi nằm trong scope đã duyệt như format, chạy seed tiếp theo hoặc thực hiện một bước kỹ thuật đã nêu không phải mở lại quyết định. Nếu user muốn chế độ chặt hơn, charter có thể yêu cầu trao đổi trước các quyết định kỹ thuật bổ sung.

### 7.2. Nội dung brainstorm

1. Problem và điều chưa rõ.
2. Evidence liên quan từ code, nguồn và findings cũ.
3. Các phương án khả thi, tradeoffs, giả định, chi phí và rủi ro.
4. Recommendation với giải thích ngắn gọn.
5. Thí nghiệm nào có thể phân biệt các phương án.
6. Quyết định cụ thể user cần chốt.

Không tạo phương án giả chỉ để đủ số lượng. Không yêu cầu agent xuất suy luận nội bộ chi tiết; cần một bản giải thích có thể đánh giá từ evidence.

Nếu chưa đủ bằng chứng, quyết định hợp lệ có thể là thực hiện exploration trong một ngân sách giới hạn, chưa chọn implementation cuối cùng.

### 7.3. Phê duyệt và revisions

- Trạng thái decision: `proposed`, `discussed`, `approved`, `rejected`, `deferred`, `superseded`.
- Lưu hướng user chọn, approved scope và bằng chứng phê duyệt có sẵn.
- Không coi im lặng hoặc nội dung do agent tự viết là user approval.
- Nếu không có transcript/message reference ổn định, ghi summary và nguồn xác nhận thực tế; không tạo message ID giả.
- Một instruction rõ ràng của user có thể duyệt sẵn cả protocol có giới hạn; không hỏi lại cho từng bước trong scope đó.
- Thay đổi material scope, phương pháp hoặc evaluation cần revision mới và phê duyệt phần thay đổi.
- Bản cũ được giữ; `supersedes`/`superseded_by` liên kết lịch sử.

## 8. Handoff bắt buộc sang session mới

### 8.1. Quy tắc trung tâm

Sau khi brainstorm được chốt, session hiện tại tạo tài liệu và **kết thúc ở bước bàn giao**. Plugin hướng dẫn user mở **một session mới** trong cùng repository, bật native Plan Mode và cung cấp tài liệu brainstorm cho session đó.

Không tiếp tục planning trong session brainstorm như đường đi mặc định. Không tự chuyển mode, không tự mở session và không báo session mới đã đọc tài liệu nếu chưa quan sát được điều đó.

Session mới có thể là Codex hoặc Claude Code. Records và tài liệu phải dùng ngôn ngữ trung lập với host.

### 8.2. Tài liệu được tạo sau brainstorm

`BRIEF.md` bao gồm:

- Task ID, document revision và trạng thái.
- Problem statement và research motivation.
- Scope, non-goals và constraints.
- Các phương án đã thảo luận và hướng đã chốt.
- Decision IDs/revisions và phần user đã phê duyệt.
- Findings, references và code entry points liên quan.
- Assumptions và open questions.
- Acceptance criteria và evaluation boundaries.
- Budget và stop conditions nếu có.

`HANDOFF.md` bao gồm:

- Đường dẫn tương đối từ project root và thứ tự đọc.
- Repo/branch/commit tại thời điểm bàn giao nếu biết; ghi trạng thái dirty.
- Task/brief/decision revisions cần dùng.
- Instructions cho **fresh session trong native Plan Mode**.
- Những quyết định đã chốt, phần còn cần planning và điều kiện quay lại brainstorm.
- Hướng dẫn phase transition từ planning sang execution.
- Liên kết tới conventions, findings và quy trình experiment logging.

`STATUS.md` của task được tạo hoặc cập nhật thành `ready_for_planning` khi đủ điều kiện.

### 8.3. Output trả cho user

Thông báo chuẩn phải chứa bốn bước:

1. Mở **session mới** của Codex hoặc Claude Code trong cùng repository.
2. Bật native Plan Mode bằng `/plan` hoặc control tương ứng của host.
3. Paste prompt bàn giao đã sinh để agent đọc Markdown.
4. Review kế hoạch; sau khi duyệt, chuyển sang execution để implement.

Prompt dùng đường dẫn thật của task, không để placeholder chưa thay. Nếu repository không có trên môi trường mới, user phải cung cấp tài liệu/code cần thiết trước khi agent có thể planning từ code.

### 8.4. Điều kiện handoff hợp lệ

- Có hướng brainstorm đã được chốt hoặc một exploration scope được duyệt rõ.
- Các đường dẫn tham chiếu tồn tại hoặc được đánh dấu là external/unavailable.
- Accepted decisions, assumptions và open questions được phân biệt.
- Session mới không cần transcript cũ để hiểu scope.
- Instructions nêu rõ phải bắt đầu ở Plan Mode và chưa được implement.
- Không chứa secrets, absolute machine-specific paths không cần thiết hoặc chi tiết held-out bị hạn chế.
- `handoff --check` báo references/revisions cũ hoặc thiếu.

## 9. Native planning và implementation

### 9.1. Trách nhiệm session mới trong Plan Mode

1. Đọc `HANDOFF.md`, `BRIEF.md`, charter và instructions liên quan.
2. Kiểm tra repository thực tế, branch, code entry points và sự khác biệt so với handoff.
3. Đọc findings được phép dùng trước khi đề xuất giải pháp.
4. Nêu lại ngắn gọn scope đã hiểu và những câu hỏi còn thiếu.
5. Lập implementation plan gắn với code hiện tại.
6. Trình bày các bước, dependencies, validation, experiment protocol và acceptance criteria.
7. Đưa plan cho user review trước khi implementation.

Native planning được phép khảo sát và tinh chỉnh chi tiết kỹ thuật trong approved direction. Nếu phát hiện cần đổi research decision, giải thích evidence và thảo luận lại thay vì âm thầm đổi hướng.

### 9.2. Lưu plan và chuyển sang execution

Không yêu cầu Plan Mode phải chỉnh repository để lưu `PLAN.md`. Host có thể có native plan artifact riêng hoặc hạn chế ghi file trong planning.

Sau khi user duyệt plan và chuyển sang execution:

1. Persist bản plan được duyệt vào `research/tasks/<task-id>/PLAN.md`.
2. Ghi plan revision, brief revision, decision revisions và approval evidence có sẵn.
3. Cập nhật task status thành `plan_approved`, rồi `implementing` khi bắt đầu sửa code.
4. Thực hiện scope đã duyệt.
5. Ghi experiments/runs/findings theo conventions.
6. Kết thúc bằng evidence, limitations và bước tiếp theo.

Nếu plan thay đổi sau approval, ghi revision. Thay đổi routine detail trong scope có thể tiếp tục; thay đổi phương pháp, evaluation hoặc acceptance criteria phải thảo luận lại.

### 9.3. Vòng đời task

| Trạng thái | Ý nghĩa |
| --- | --- |
| `brainstorming` | Đang thảo luận; chưa chốt hướng. |
| `ready_for_planning` | Có brief/handoff, chờ user mở session mới và bắt đầu native planning. |
| `planning` | Session mới đã bắt đầu planning; cần ghi nhận thực tế, không tự suy diễn. |
| `plan_approved` | User đã duyệt plan; persist plan khi vào execution. |
| `implementing` | Đang triển khai scope đã duyệt. |
| `evaluating` | Đang đánh giá bằng protocol liên quan. |
| `completed` | Acceptance criteria đã được kiểm tra; còn limitations được ghi rõ. |
| `blocked` | Không thể tiếp tục, có lý do và next action. |
| `paused` | Tạm dừng có chủ đích. |
| `cancelled` | Dừng task, vẫn giữ records và findings. |

Không tự chuyển task thành `planning` chỉ vì đã xuất prompt. `resume` đọc records; không coi trạng thái trong chat là nguồn duy nhất.

## 10. Convention về implementation tổng quát

### 10.1. Yêu cầu cho thay đổi quan trọng

Mỗi thay đổi thuật toán/phương pháp hoặc bug fix quan trọng phải trả lời:

1. Root cause đã xác nhận hoặc hypothesis nào đang được kiểm chứng?
2. Giải pháp xử lý lớp vấn đề nào?
3. Giả định và giới hạn áp dụng là gì?
4. Có phụ thuộc sample ID, repository name hoặc expected output không?
5. Có đối chứng hoặc counterexample nào phân biệt sửa root cause với patch theo triệu chứng?
6. Verification nào vượt ra ngoài case đã dùng để phát hiện vấn đề?

Không bắt mọi thay đổi nhỏ phải có báo cáo dài. Mức tài liệu tỷ lệ với tác động nghiên cứu và độ bất định.

### 10.2. Special cases

Không chấp nhận nhánh đặc biệt chỉ nhằm tăng điểm trên sample đã quan sát, chẳng hạn hardcode expected answer theo repository name.

Adapter theo public API version, format hoặc capability có thể hợp lệ nếu dựa trên thuộc tính kỹ thuật có ý nghĩa và được kiểm tra trên các trường hợp phù hợp. Việc dùng tên hoặc ID không tự động chứng minh overfit; cần đánh giá vai trò của nó.

Tests có thể gồm regression case, boundary cases, property/metamorphic checks hoặc fixtures độc lập tùy thay đổi. Không yêu cầu một ma trận kiểm thử vô hạn cho mọi fix.

### 10.3. Generalization review

Review tạo assessment gồm scope, evidence, special cases, counterexamples, leakage concerns và open risks. Không xuất nhãn tuyệt đối như “proven general” hoặc “guaranteed no overfitting”.

## 11. Evaluation integrity

### 11.1. Vai trò dữ liệu

| Vai trò | Sử dụng |
| --- | --- |
| `development` | Debug, exploration và phát triển phương pháp. |
| `validation` | Chọn cấu hình hoặc phương án theo protocol đã thống nhất. |
| `held_out_test` | Đánh giá xác nhận sau khi đóng băng phương pháp. |

Validation feedback là một phần hợp lệ của development khi được khai báo. Việc theo dõi nhiều vòng validation vẫn có thể làm giảm mức độc lập của đánh giá; ghi exposure thay vì tuyên bố validation luôn sạch.

### 11.2. Quy tắc

- Ghi phiên bản dataset, split, provenance và mục đích truy cập.
- Ghi những lần exposure đã biết; không giả định plugin biết toàn bộ lịch sử bên ngoài.
- Freeze code/config/evaluator/metric và selection rule trước confirmatory evaluation.
- Không đổi metric hoặc loại failures sau khi thấy kết quả mà không ghi protocol revision.
- Không cherry-pick seed tốt nhất làm kết quả đại diện nếu protocol không quy định như vậy.
- Khi dùng held-out failures để sửa phương pháp, ghi nhận dữ liệu đó đã thành development feedback cho vòng sau.
- Muốn khôi phục một đánh giá xác nhận độc lập, cần fresh holdout hoặc thiết kế đánh giá phù hợp; không chỉ đổi tên split.
- Nếu benchmark public đã có nguy cơ contamination từ trước, ghi provenance/exposure và giới hạn kết luận; plugin không thể đảo ngược việc tiếp xúc đã xảy ra.
- Nếu sửa evaluator, lưu version và lý do; áp dụng quy tắc đánh giá lại nhất quán cho các phương pháp so sánh.

### 11.3. Memory và held-out information

Findings có `visibility` để phân biệt development memory với restricted evaluation analysis. Recall mặc định không đưa restricted held-out details vào context phát triển.

Đây là workflow boundary trong MVP. Muốn thực thi access isolation thật cần tách account/process/storage và quyền truy cập; chỉ tách thư mục không đủ.

## 12. Mô hình dữ liệu

### 12.1. Common fields

Mọi entity có `schema_version`, `id`, `revision`, `created_at`, `updated_at`, `task_id` nếu liên quan, và references có kiểu rõ ràng.

- Thời gian lưu theo UTC ISO 8601; UI có thể hiển thị theo timezone người dùng.
- IDs phải duy nhất khi chạy đồng thời; dùng UUID hoặc ULID, có prefix theo loại.
- Revision tăng khi nội dung có ý nghĩa thay đổi; giữ các revision cũ hoặc append-only change records.
- Không dùng filename hoặc timestamp đơn lẻ làm uniqueness guarantee.
- ID trong ví dụ là minh họa, không phải record đã tồn tại.

### 12.2. Entities

| Entity | Trách nhiệm |
| --- | --- |
| Task | Điều phối brainstorm, handoff, planning, implementation và evaluation. |
| Decision | Vấn đề, options, evidence và lựa chọn được duyệt. |
| Experiment | Hypothesis và protocol trước khi chạy. |
| Run | Một lần thực thi của một experiment revision cụ thể. |
| Finding | Observation, hypothesis, lesson hoặc correction có scope. |
| Claim | Kết luận đưa vào report/paper với evidence và giới hạn. |

### 12.3. Decision

Các fields bổ sung: `question`, `options`, `selected_option`, `status`, `evidence_refs`, `approved_scope`, `approval_evidence`, `revisit_when`, `supersedes`.

Một approved decision không đồng nghĩa mọi implementation tương lai đã được duyệt. Approved scope phải đủ cụ thể để xác định việc nào được tiếp tục.

### 12.4. Experiment

Các fields bổ sung:

| Field | Nội dung |
| --- | --- |
| `decision_refs` | Decisions và revisions liên quan. |
| `hypothesis` | Mệnh đề cần kiểm chứng. |
| `baseline` | Baseline và version/config cần dùng. |
| `intervention` | Yếu tố thay đổi và các confounders cần kiểm soát. |
| `dataset_refs` | Dataset/split version và vai trò. |
| `primary_metric` | Metric, chiều tốt hơn, đơn vị, denominator. |
| `secondary_metrics` | Metrics bổ sung, không âm thầm thay primary. |
| `evaluation_unit` | Repository, task, user hoặc đơn vị nghiên cứu phù hợp. |
| `repetitions` | Seeds/lặp lại; phân biệt stochastic repeats với đơn vị độc lập. |
| `budget` | Run limit và/hoặc time, token, cost limits. |
| `success_criteria` | Điều kiện đánh giá hypothesis. |
| `stop_conditions` | Khi nào dừng theo protocol. |
| `failure_handling` | Retry, missing data và loại mẫu được xử lý ra sao. |
| `analysis_plan` | Cách aggregate/compare, uncertainty và selection rule. |
| `status` | `draft`, `approved`, `running`, `closed`, `superseded`. |

Thay protocol sau khi nhìn kết quả cần revision mới, nêu các kết quả đã quan sát và phần thay đổi. Run cũ tiếp tục tham chiếu revision cũ.

### 12.5. Run

Các nhóm thông tin:

- Identity: experiment ID/revision, task ID, parent run nếu retry.
- Code: commit, dirty status, patch/snapshot và checksums khi có.
- Inputs: config snapshot, input references và dataset/evaluator versions.
- Execution: argv, working directory, start/end times, exit code và cancellation reason.
- Environment: dependency lock/container, runtime và hardware liên quan.
- Model: provider, model identifier, parameters, routing metadata có thể thu được.
- Outputs: stdout/stderr, metrics, artifact paths/URIs và checksums.
- Accounting: duration, tokens/cost nếu có; nếu thiếu ghi `null` cùng lý do.
- Interpretation: execution status, research outcome và analysis status riêng biệt.

`execution_status`: `queued`, `running`, `completed`, `failed`, `cancelled`, `interrupted`.

`research_outcome`: `positive`, `negative`, `inconclusive`, `not_assessed`.

`analysis_status`: `pending`, `analyzed`, `deferred`.

Một run có thể là `completed` và `negative`. Run lỗi hạ tầng thường là `failed` và `not_assessed`; không tự động coi đó là bằng chứng bác bỏ hypothesis.

### 12.6. Finding

Fields bổ sung: `kind`, `statement`, `evidence_refs`, `scope`, `limitations`, `confidence`, `alternative_explanations`, `next_action`, `visibility`, `supersedes`.

- `kind`: `observation`, `hypothesis`, `lesson`, `correction`.
- `confidence`: `tentative`, `supported`, `replicated`; đây là nhãn mô tả, không phải probability hay significance level.
- `visibility`: `development`, `restricted_evaluation`.
- Một finding có thể tổng hợp nhiều runs; không ép mỗi run tạo một bài học mới.

Finding tách observation và interpretation. Ví dụ “ba runs cho thấy coverage cao hơn” chưa tự chứng minh nguyên nhân là “retrieval tốt hơn”.

### 12.7. Claim

Fields bổ sung: `statement`, `scope`, `evidence_refs`, `counterevidence_refs`, `limitations`, `status` và `report_refs`.

Claim phải có strength tương ứng evidence. Khi findings bị correction hoặc superseded, `doctor`/report review cảnh báo claims phụ thuộc cần xem lại, không tự xóa claim cũ.

## 13. Experiment runner và ghi nhận mọi lần thử

### 13.1. Entry point

```json
{"operation":"run.start","root":"/absolute/project","arguments":{"experiment":"actual-experiment-ID","argv":["python","scripts/evaluate.py","--config","configs/experiment.toml"]}}
```

JSON trên là giao tiếp nội bộ do agent tạo và gửi trong session; agent thay ID/path bằng giá trị thực. `argv` thuộc dự án nghiên cứu của user, không phải CLI LabLedger.

### 13.2. Lifecycle

1. Validate experiment revision, required metadata và approved scope.
2. Tạo run ID và manifest trước khi khởi chạy process.
3. Snapshot config và metadata có thể thu được.
4. Ghi stdout/stderr ra file theo stream; không giữ toàn bộ log trong RAM.
5. Theo dõi process, duration và budget có thể thực thi.
6. Khi kết thúc, persist execution status, exit code và artifacts.
7. Để research outcome là `not_assessed` cho tới khi có analysis.
8. Mark `analysis_status=pending` và hiển thị next action.

### 13.3. Failures, retry và interrupted runs

- Retry luôn tạo run mới, có `parent_run_id` và lý do.
- Không ghi đè run thất bại bằng kết quả retry thành công.
- Cancellation cố gắng dừng process group để tránh worker mồ côi; cách thực hiện cần phù hợp OS.
- Khi runner crash hoặc máy tắt, run có thể còn `running`; `resume`/`doctor` đối chiếu execution identity và timestamps để reconcile.
- Không dựa riêng vào PID vì PID có thể được tái sử dụng; nếu không xác định được trạng thái thì báo cần reconcile.
- Không tự relaunch hoặc rerun expensive experiment khi resume.
- Khi xác nhận process đã dừng nhưng không có kết quả hoàn chỉnh, ghi `interrupted` cùng lý do và evidence có sẵn.

### 13.4. Probes và external runs

Thao tác thăm dò nhanh có thể lưu lightweight probe record: câu hỏi, command/observation, thời điểm và kết quả. Nếu probe ảnh hưởng tới quyết định hoặc claim, phải liên kết vào evidence và nâng mức ghi nhận khi cần.

Run ngoài wrapper có thể import bằng `run import`; metadata thiếu phải ghi là thiếu, không suy đoán. Plugin chỉ bảo đảm ghi các run đi qua entry points đã được tích hợp.

### 13.5. Reproducibility

Run manifest ghi `reproducibility_status`: `complete`, `partial`, `unavailable`, cùng danh sách thông tin còn thiếu. “Complete” ở đây nghĩa là đủ metadata theo policy, không phải bảo đảm bit-for-bit reproducibility.

Nếu repo dirty, chỉ lưu commit là không đủ: cần patch/snapshot của inputs liên quan, bao gồm untracked files cần thiết nếu được phép. Không tự snapshot secrets, datasets hạn chế hoặc toàn filesystem. Khi không thể lưu, ghi hạn chế.

Model seed không bảo đảm deterministic output của hosted API. Lưu identifier/parameters và các response metadata có sẵn; không tuyên bố backend version đã được pin nếu provider không cung cấp.

## 14. Findings và research memory

### 14.1. Khi nào phải ghi

- Sau analysis của experiment.
- Khi phát hiện failure mode có khả năng gặp lại.
- Khi bác bỏ một giả định hoặc có counterexample.
- Khi một kết quả không đủ bằng chứng để kết luận.
- Khi sửa lỗi hạ tầng ảnh hưởng evaluation.
- Trước khi đóng task hoặc bàn giao nếu còn insight chưa persist.

Mọi run phải có analysis status. Nếu chưa phân tích, giữ `pending`; nếu chủ động hoãn, ghi `deferred` cùng lý do. Không bắt agent bịa finding để làm sạch checklist.

### 14.2. Recall

Trước một hướng mới hoặc trước khi lặp lại hướng cũ, tìm theo component, failure type, hypothesis, method, dataset/task và environment.

Kết quả recall phải trả: finding ID, scope, evidence, limitations, trạng thái còn hiệu lực và lý do liên quan. Chỉ nạp subset cần thiết vào context; không đọc toàn bộ lịch sử mặc định.

Một kết quả âm có thể không áp dụng khi model, data, budget hoặc implementation thay đổi. Agent phải giải thích khác biệt, không biến memory thành danh sách cấm vĩnh viễn.

### 14.3. Correction

Khi bằng chứng mới bác bỏ finding cũ:

1. Tạo correction record có evidence mới.
2. Liên kết finding cũ bằng `supersedes`.
3. Đánh dấu dependent claims/decisions cần review.
4. Giữ raw evidence và wording cũ để truy lại.

## 15. Analysis và reporting

### 15.1. So sánh có ý nghĩa

- Kiểm tra task set, dataset/evaluator version, budget và config có tương thích không.
- Nếu khác, nêu mismatch trước khi diễn giải improvement.
- Báo numerator/denominator, missing samples, failed runs và exclusions.
- Phân biệt evaluation unit độc lập với repetitions/seeds.
- Không coi nhiều seeds trên cùng repository là nhiều repositories độc lập.
- Khi phù hợp, dùng paired comparison trên cùng cases và uncertainty ở đúng cấp phân tích.
- Ghi exploratory versus confirmatory analysis và các lựa chọn sau khi quan sát data.
- Kết quả không đủ evidence phải được báo là inconclusive thay vì ép positive/negative.

### 15.2. Báo cáo

Report gồm research question, protocol, compared versions, results, failures, uncertainty, scope, limitations và next decisions. Mỗi claim quan trọng có links tới records/artifacts/nguồn.

Không tự bỏ kết quả xấu khỏi report. Có thể chọn nhóm theo protocol, nhưng phải ghi selection rule và phần không được đưa vào aggregate.

## 16. Bộ action trong session và backend nội bộ

### 16.1. User-facing actions

| Action | Trách nhiệm | Priority |
| --- | --- | --- |
| `init` | Scaffold và charter. | P0 |
| `brainstorm` | Evidence, options và decision với user. | P0 |
| `handoff` | Xuất tài liệu và instructions mở session mới với native Plan Mode. | P0 |
| `recall` | Truy hồi findings liên quan. | P0 |
| `run` | Theo dõi execution và artifacts. | P0 |
| `analyze` | Diễn giải results và tạo findings. | P0 |
| `resume` | Khôi phục trạng thái từ records, nêu next action. | P0 |
| `doctor` | Validation, stale refs và capability report. | P0 |
| `report` | Tổng hợp claims và evidence. | P1 |
| `review-generalization` | Assessment về scope, special cases và leakage. | P1 |

Không có action `plan` hoặc `implement` riêng của LabLedger. Planning và implementation thuộc host native workflow. Có thể có internal plan-record persistence API; API đó không phải planning engine.

### 16.2. Backend nội bộ

Mọi thao tác do agent gọi trong session qua helper nằm trong plugin. Không cung cấp executable `labledger`, entry point `python -m labledger`, hoặc yêu cầu user cài wheel/core riêng.

Request JSON có `operation`, `root` tuyệt đối, optional `arguments`, và `payload` khi operation yêu cầu. Agent tự tạo payload từ repo, bằng chứng và hội thoại; user chỉ trao đổi mục tiêu và quyết định. Response chứa `ok`, `code`, và `result` hoặc `error`.

| Operation nội bộ | Chức năng |
| --- | --- |
| `init` | Preview/apply scaffold theo charter đã thống nhất. |
| `task.new`, `task.update`, `task.get` | Task metadata và trạng thái. |
| `decision.new`, `decision.update` | Decision draft, approval và revisions. |
| `handoff` | Generate/validate handoff và paste prompt. |
| `task.attach-plan` | Persist plan sau approval và chuyển sang execution. |
| `experiment.new`, `experiment.update` | Protocol draft và revisions. |
| `run.start`, `run.import`, `run.annotate`, `run.reconcile` | Chạy, nhập, phân tích và đối soát attempts. |
| `finding.add`, `claim.add`, `probe.add`, `exposure.add`, `review.add` | Lưu observations, claims, exposure và assessments. |
| `artifact.add`, `artifact.redact`, `artifact.tombstone` | Artifact metadata và derivatives. |
| `recall`, `status`, `resume`, `report` | Truy hồi, trạng thái và báo cáo. |
| `doctor`, `cache.rebuild`, `policy.get`, `policy.update` | Diagnostics, derived cache và research policy. |
| `schema`, `version` | Schema và phiên bản backend đi kèm plugin. |

Backend dùng mã `0` thành công; `2` input/schema invalid; `3` conflict; `4` thiếu prerequisite; `5` storage/integration failure. `run.start` trả `1` khi execution không thành công, `130` khi hủy, cùng durable run record. Child exit code giữ riêng trong record. JSON protocol chi tiết được duy trì tại `src/labledger/resources/backend.md` và đóng gói cho cả hai host.

### 16.3. Host command mapping

Claude Code dùng `/labledger:<action>`. Codex adapter tạo skill tên `labledger-<action>` để gọi bằng `$labledger-<action>` theo khả năng host. Hai adapter trỏ tới cùng workflow và core.

`brainstorm` sau khi user chốt có thể tự gọi handoff workflow; `handoff` vẫn tồn tại để regenerate/validate docs hoặc xuất lại prompt. Không cần bắt user gõ thêm lệnh khi dữ liệu đã đủ.

## 17. Cấu hình đề xuất

```toml
schema_version = 1

[project]
name = "my-research-project"
research_dir = "research"
artifacts_dir = "artifacts/runs"

[workflow]
discuss_research_decisions = true
fresh_session_after_brainstorm = true
use_native_plan_mode = true
persist_approved_plan_on_execution = true

[memory]
recall_before_new_approach = true
default_visibility = "development"
exclude_restricted_evaluation = true

[experiments]
require_protocol = true
require_approved_scope = true
capture_stdout = true
capture_stderr = true
capture_git_metadata = true
capture_config_snapshot = true
capture_all_environment_variables = false

[storage]
atomic_writes = true
preserve_history = true
raw_artifacts_in_git = false

[adapters]
codex = true
claude_code = true
hooks = "optional"
```

Các flags trên là đề xuất cho schema v1. Các nguyên tắc cốt lõi như bảo toàn history không nên bị tắt âm thầm; thay đổi policy cần ghi vào charter/config history. `fresh_session_after_brainstorm` mặc định bật theo workflow đã thống nhất.

## 18. Templates

### 18.1. BRIEF.md

```markdown
# Research brief

Task: <task-id>
Revision: <revision>
Status: ready_for_planning
Decision references: <ids and revisions>

## Problem and motivation
<What problem are we addressing, and why does it matter?>

## Scope and non-goals
<Boundaries, assumptions, and exclusions.>

## Evidence reviewed
<Relevant code, references, findings, and counterevidence.>

## Options considered
<Viable alternatives and tradeoffs.>

## Agreed direction
<The user's chosen direction and approved scope.>

## Constraints
<Generalization, evaluation integrity, budget, compatibility.>

## Acceptance criteria
<Observable checks that define completion.>

## Open questions
<Questions the new planning session should resolve.>

## Relevant files and records
<Project-relative paths, IDs, and external sources.>
```

### 18.2. HANDOFF.md

```markdown
# Fresh session handoff

Start a NEW Codex or Claude Code session in this repository.
Enable the host's native Plan Mode before starting this task.
Do not rely on the previous brainstorming conversation.

Task: <task-id>
Brief revision: <revision>
Repository state at handoff: <branch, commit, dirty status, or unknown>

## Read first
1. Applicable repository instructions, including AGENTS.md or CLAUDE.md.
2. research/CHARTER.md
3. research/tasks/<task-id>/BRIEF.md
4. research/tasks/<task-id>/STATUS.md
5. The relevant decisions and findings referenced in BRIEF.md.

## Planning task
Inspect the actual repository and develop an implementation plan
within the agreed research direction.

Identify components, implementation steps, dependencies,
verification procedures, experiment protocols, acceptance criteria,
generalization risks, and unresolved questions.

Separate agreed decisions from assumptions and open questions.
Discuss material changes to research decisions before adopting them.
Present the plan for user review before implementation.

## Transition to execution
After user approval and transition out of planning, persist the approved
plan to research/tasks/<task-id>/PLAN.md before changing research code.
Record its brief and decision revisions and available approval evidence.

During execution, follow LabLedger conventions, register experiments,
preserve failed attempts, record findings, and update task status.
```

### 18.3. Prompt user paste trong session mới

```text
I am starting a NEW session for a task that was brainstormed previously.
Use native Plan Mode for this task.

Read research/tasks/<task-id>/HANDOFF.md and the files it references.
Treat those documents as the durable task context; do not assume access
to the previous conversation.

Inspect the repository and propose an implementation plan within the
agreed research direction. Discuss any material change to that direction
with me. Present the plan for review before implementation.

After I approve the plan and we switch to execution, persist it to the
task's PLAN.md, implement it, and maintain LabLedger experiment records,
findings, and task status throughout the work.
```

Plugin thay `<task-id>` và mọi placeholder khác bằng giá trị thật khi generate. Cụm “Use native Plan Mode” trong prompt không tự chuyển host mode: user vẫn cần bật mode bằng control của host.

### 18.4. PLAN.md

```markdown
# Approved implementation plan

Task: <task-id>
Plan revision: <revision>
Based on brief revision: <revision>
Decision references: <ids and revisions>
Approval evidence: <available evidence, not an invented message ID>

## Goal and scope
<Approved outcome and boundaries.>

## Repository observations
<Actual code structure and relevant constraints.>

## Implementation steps
<Ordered steps with dependencies and expected outputs.>

## Verification and experiments
<Checks, protocols, metrics, baselines, and data boundaries.>

## Acceptance criteria
<Completion criteria and required evidence.>

## Risks and revisit conditions
<Assumptions and material changes requiring discussion.>
```

### 18.5. STATUS.md của task

```markdown
# Task status

Task: <task-id>
State: <state>
Updated at: <timestamp>
Active brief revision: <revision>
Active plan revision: <revision or not yet approved>

## Completed
<Completed work and evidence references.>

## In progress
<Current work and active runs.>

## Blockers and open questions
<Unresolved items and who/what can resolve them.>

## Findings and pending analysis
<Finding references and runs still needing analysis.>

## Next action
<One concrete next action, including opening a new planning session
when the task is ready_for_planning.>
```

### 18.6. Finding example

Ví dụ minh họa dưới đây không phải kết quả nghiên cứu đã quan sát:

```json
{
  "schema_version": 1,
  "id": "FND-example",
  "revision": 1,
  "task_id": "TASK-example",
  "created_at": "2026-11-02T00:00:00Z",
  "updated_at": "2026-11-02T00:00:00Z",
  "kind": "observation",
  "statement": "A larger retrieval budget improved coverage in the evaluated subset but increased latency.",
  "evidence_refs": [
    {"type": "run", "id": "RUN-example-a"},
    {"type": "run", "id": "RUN-example-b"}
  ],
  "scope": "The development subset and configuration recorded by the referenced runs.",
  "limitations": ["Not evaluated on held-out data."],
  "confidence": "tentative",
  "alternative_explanations": ["Different retrieved context may contribute to the result."],
  "next_action": "Plan a controlled comparison within the approved budget.",
  "visibility": "development",
  "supersedes": null
}
```

## 19. Agent conventions dùng chung

Đoạn instructions cốt lõi để adapter tích hợp, kèm links tới workflow chi tiết:

```text
Before making a research decision, review relevant evidence,
present viable options and tradeoffs, and obtain the user's decision.
Act within an already approved scope without reopening routine steps.

After an agreed brainstorm, write a durable brief and handoff documents.
Instruct the user to open a NEW Codex or Claude Code session in the same
repository, enable native Plan Mode, and provide the handoff prompt.
Finish the brainstorming session at the handoff boundary.

In the new planning session, read the handoff and its references,
inspect the repository, and propose a plan for review.
Discuss material departures from agreed research decisions.

After user approval and transition to execution, persist the approved
plan before changing research code.

Implement solutions for the stated problem class.
Document assumptions, boundaries, and evidence beyond the triggering case.
Do not introduce benchmark-specific behavior solely to improve scores.

Register experiments before execution.
Preserve positive, negative, inconclusive, failed, and interrupted attempts.
Separate execution success from research success.

Distinguish observations, hypotheses, and conclusions.
Link claims to evidence and state scope and limitations.

Recall relevant findings before repeating an approach.
Preserve corrections and superseded conclusions in the research history.

Keep development feedback separate from held-out confirmation.
Record evaluation exposure and protocol changes.

Maintain durable task status so another session can continue from records.
Never claim that an unobserved run, approval, or session transition occurred.
```

Các conventions này áp dụng trong phạm vi quyền của plugin và instructions cấp cao hơn của host. Không viết prompt yêu cầu bỏ qua policy, permissions hoặc restrictions của runtime.

## 20. Tính toàn vẹn, concurrency và dữ liệu nhạy cảm

- Atomic write cho từng file; lock hoặc optimistic revision checks cho records có thể bị ghi đồng thời.
- Multi-file operations dùng journal/transaction manifest để phát hiện partial state và reconcile.
- Cache/index không là canonical store; mất cache không làm mất research history.
- Sau run completion, bổ sung annotation/correction thay vì sửa âm thầm raw artifacts.
- Checksums giúp phát hiện thay đổi; không phải chống giả mạo nếu actor có cùng quyền ghi.
- Không capture toàn bộ environment, credentials, API keys hoặc nội dung private không cần thiết.
- Redaction phải đánh dấu phần dữ liệu đã redact; không giả vờ raw log còn nguyên vẹn.
- Không tự upload research data ra dịch vụ ngoài.
- Hooks không tự cấp thêm quyền, không tự bỏ approval và không báo là đã chặn mọi đường thực thi.
- Khi không có capability cần thiết, `doctor` báo unsupported/partial và đưa workflow skill trong session thay thế.

## 21. Acceptance criteria

| ID | Tình huống | Kết quả bắt buộc |
| --- | --- | --- |
| AC-01 | Chạy init hai lần | Không duplicate hoặc làm mất nội dung. |
| AC-02 | Init trong repo có conventions | Giữ nội dung user và báo conflict cụ thể. |
| AC-03 | Chạy dry-run | Không sửa file. |
| AC-04 | Idea chưa chốt | Agent thảo luận; decision chưa được ghi approved. |
| AC-05 | Brainstorm đã chốt | Có brief, handoff, task status và prompt đã điền đủ. |
| AC-06 | Kết thúc brainstorm | Hướng dẫn mở session mới; không bắt đầu implementation trong session này. |
| AC-07 | Fresh planning session | Hiểu được task từ docs và code, không cần chat cũ. |
| AC-08 | Handoff chưa được dùng | Status không tự chuyển thành planning. |
| AC-09 | Native planning cần đổi hướng | Discuss phần thay đổi trước khi adopt. |
| AC-10 | User duyệt plan | Persist plan lúc vào execution, rồi implement trong scope. |
| AC-11 | Plan Mode hạn chế ghi file | Workflow không phụ thuộc việc planning sửa repository. |
| AC-12 | Brief/decision revision thay đổi | Handoff/plan stale được phát hiện và cần review phần liên quan. |
| AC-13 | Registered run bắt đầu | Manifest tồn tại trước child process. |
| AC-14 | Run completed nhưng metric giảm | Execution và research outcome được lưu riêng. |
| AC-15 | Run crash hoặc cancelled | Giữ metadata và logs có sẵn. |
| AC-16 | Runner mất kết nối hoặc bị kill | Resume phát hiện run cần reconcile, không báo success. |
| AC-17 | Retry | Tạo run ID mới và parent reference. |
| AC-18 | Chưa đủ evidence | Ghi inconclusive/not_assessed hoặc pending; không bịa finding. |
| AC-19 | Lặp lại hướng đã thử | Recall scope/evidence cũ và giải thích khác biệt. |
| AC-20 | Finding bị bác bỏ | Correction giữ lịch sử và cảnh báo dependent claims. |
| AC-21 | Dùng test feedback để sửa | Ghi exposure và điều chỉnh interpretation. |
| AC-22 | Hai run đồng thời | Không trùng ID, ghi đè manifest hoặc trộn logs. |
| AC-23 | External run import thiếu metadata | Thiếu được ghi rõ, không tự suy đoán. |
| AC-24 | Đổi Codex sang Claude Code hoặc ngược lại | Dùng lại cùng records và handoff. |
| AC-25 | Hooks không khả dụng | Workflow skill trong session vẫn hoạt động với backend đi kèm. |
| AC-26 | Report kết quả | Không bỏ failures; claims liên kết được tới evidence. |
| AC-27 | Recall trong development | Không tự inject restricted evaluation findings. |
| AC-28 | Restore/rebuild cache | Records gốc còn nguyên và index rebuild được. |

## 22. Kế hoạch triển khai

### Milestone 1 — Scaffold và durable records

- Models/schema versions, IDs, filesystem storage, revisions và validation.
- Init, charter, task/decision/finding records, status và doctor.
- Managed instruction sections và conflict-safe updates.
- Fixtures cho repo mới, repo đã có instructions và schema conflicts.

**Hoàn thành khi:** tạo và duy trì một project nhỏ mà không mất dữ liệu khi init lặp lại hoặc update records.

### Milestone 2 — Brainstorm và fresh-session handoff

- Shared brainstorm workflow.
- Brief/handoff/status templates và generator.
- Paste prompt cho session mới + native Plan Mode.
- Validation revisions/references và entry conventions cho execution.
- Hai host adapters dùng cùng source workflow.

**Hoàn thành khi:** từ một brainstorm, có thể bắt đầu session mới trên từng host, lập plan và triển khai trong agreed scope mà không cần chat cũ.

### Milestone 3 — Runner và findings loop

- Experiment protocol và revision links.
- Runner, stream logs, snapshots, concurrent runs, cancellation và reconcile.
- External run import với incomplete metadata.
- Analysis status, findings persistence, recall và correction.

**Hoàn thành khi:** một experiment có cả run tốt, xấu và crash vẫn có lịch sử đầy đủ và recall được findings liên quan.

### Milestone 4 — Reporting và integration nâng cao

- Generalization review, claims và report generation.
- Evaluation exposure records và restricted-memory policy.
- Optional hooks theo capability matrix.
- Packaging, installation instructions và compatibility tests theo release.

Dashboard, hosted artifact storage và tích hợp external trackers chỉ thêm khi workflow local đã ổn định.

## 23. Chiến lược kiểm thử

### 23.1. Core correctness

- Idempotent init và managed block conflicts.
- Schema validation, transitions và stale revision guards.
- Atomic writes, concurrent run IDs và partial operation recovery.
- Runner failure/cancellation/interruption, stdout/stderr streaming.
- References, history preservation và index rebuild.
- Visibility filtering và redaction behavior.

### 23.2. Workflow evaluation trên từng host

Dùng tasks thực tế ở mức nhỏ, có positive và negative cases:

- Brainstorm một phương pháp có nhiều lựa chọn hợp lệ.
- Sửa một failure class với nhiều instances, có case độc lập.
- Tiếp tục hướng đã thất bại nhưng điều kiện mới khác.
- Handoff sang session mới không có chat cũ.
- Planning phát hiện decision không khả thi.
- Run hoàn tất nhưng kết quả âm; run lỗi hạ tầng.

Chấm hành vi quan sát được: đọc docs, đúng scope, thực hiện handoff, hỏi đúng decision, giữ failures và dẫn chứng claims. Theo dõi chi phí context, số câu hỏi không cần thiết và khả năng agent lặp lại nghiên cứu đã có.

Không thiết kế test chỉ để agent nhắc lại exact wording của conventions. Giữ các tình huống đánh giá riêng với ví dụ dùng để viết/tinh chỉnh skill để kiểm tra khả năng tổng quát của workflow.

## 24. Ví dụ end-to-end

Ví dụ giả định: researcher muốn cải thiện context retrieval cho coding agent trên repository lớn.

1. Trong session A, user chạy brainstorm. Agent recall findings và so sánh các hướng retrieval phù hợp.
2. User chọn kiểm chứng một hướng trong development subset, với budget giới hạn và baseline cụ thể.
3. LabLedger ghi decision, `BRIEF.md`, `HANDOFF.md` và task status `ready_for_planning`.
4. Session A trả instructions mở **session B mới**, bật native Plan Mode và paste prompt đọc handoff; không implement ngay.
5. Session B đọc docs, khảo sát code và đề xuất plan. Nếu phát hiện data pipeline không đáp ứng giả định, trao đổi trước khi đổi hướng.
6. User duyệt plan và chuyển session B sang execution.
7. Agent lưu `PLAN.md`, cập nhật status, implement trong scope và tạo experiment protocol.
8. Runner ghi từng lần chạy; một run crash vẫn giữ record, retry có ID mới.
9. Analysis cho thấy kết quả tăng trên một nhóm cases nhưng latency xấu hơn; finding lưu cả hai quan sát và giới hạn.
10. Researcher chốt bước tiếp theo dựa trên evidence. Session sau đọc status/findings thay vì lặp lại cùng thử nghiệm một cách vô thức.

## 25. Những quyết định thiết kế đã chốt trong spec

| Quyết định | Nội dung |
| --- | --- |
| Tên đề xuất | LabLedger; plugin slug `labledger`, chỉ dùng trong coding-agent session. |
| Host mục tiêu | Codex và Claude Code. |
| Planning | Dùng native Plan Mode. |
| Implementation | Dùng execution workflow của host sau user approval. |
| Boundary sau brainstorm | Persist Markdown và hướng dẫn mở session mới. |
| Context của session mới | Handoff/brief/records và repository, không phụ thuộc transcript cũ. |
| Lưu plan | Persist approved plan khi chuyển sang execution. |
| Core storage | File-based, versioned schemas, history-preserving records. |
| Research memory | Findings có scope, evidence, correction và visibility. |
| Run semantics | Tách execution status và research outcome. |
| Generalization | Đánh giá trong declared scope, không tuyên bố bảo đảm mọi trường hợp. |
| Evaluation | Ghi vai trò dữ liệu, exposure và protocol changes. |
| Enforcement | Instructions + bundled backend checks; hooks tùy host, không là bảo đảm tuyệt đối. |

## 26. Tài liệu host tham khảo

Các nguồn dưới đây dùng để tham khảo cơ chế host đã kiểm tra trong quá trình xây dựng spec. Command names và cấu trúc nội bộ của LabLedger trong tài liệu là thiết kế đề xuất.

- [OpenAI — Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [OpenAI — Submit your Claude Code plugin to OpenAI](https://developers.openai.com/plugins/guides/submit-claude-plugin)
- [ChatGPT Learn — Build skills](https://learn.chatgpt.com/docs/build-skills)
- [ChatGPT Learn — Developer commands](https://learn.chatgpt.com/docs/developer-commands)
- [ChatGPT Learn — Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Claude Code — Plugins overview](https://code.claude.com/docs/en/plugins)
- [Claude Code — Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code — Common workflows, Plan before editing](https://code.claude.com/docs/en/common-workflows#plan-before-editing)
- [Claude Code — Hooks reference](https://code.claude.com/docs/en/hooks)
- [Claude Code — Project memory and instructions](https://code.claude.com/docs/en/memory)

Trước khi release, xác minh lại package metadata, command discovery và native planning behavior trên chính phiên bản Codex/Claude Code được tuyên bố hỗ trợ. Workflow nghiên cứu và file formats của LabLedger phải hoạt động được khi optional host integrations không có.
