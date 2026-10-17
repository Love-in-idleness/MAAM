# 获取、开发与发布 / Clone, develop, and publish

项目仓库为 [Love-in-idleness/MAAM](https://github.com/Love-in-idleness/MAAM)；目前为私有仓库，访问需要相应 GitHub 账户权限。
The project repository is [Love-in-idleness/MAAM](https://github.com/Love-in-idleness/MAAM); it is currently private, so access requires an authorised GitHub account.

在已配置 GitHub 身份验证的本机执行以下命令获取代码并验证计算核心。
On a machine with GitHub authentication configured, clone the repository and validate the calculation core as follows.

```bash
git clone https://github.com/Love-in-idleness/MAAM.git
cd MAAM
python -m unittest discover -s tests -v
python scripts/verify_results.py
python -m maam rank --corpus examples/toy_corpus.json --format text
```

对现有仓库提交修改时，按常规 Git 流程建立分支、提交并推送；Python 工作流会检查测试与已提交的数值结果。
For changes to the existing repository, use the normal Git branch, commit, and push workflow; the Python workflow checks tests and the committed numerical reports.

Lean 适配器有独立的 `Lean adapter` 工作流，相关代码变化时自动运行，也可手动触发；Lean 4.24.0 的小命题检查已经通过，记录见 [远程验证](../results/remote_validation.json)。
The separate `Lean adapter` workflow runs on relevant code changes and can also be triggered manually; its small-proposition check on Lean 4.24.0 has passed, as recorded in [remote validation](../results/remote_validation.json).

`results/validation.json` 记录的是本地验证，不会因文件被推送就自动变成远程 CI 运行记录；远程结果以 GitHub Actions 的实际记录为准。
`results/validation.json` records local validation, and pushing that file does not turn it into a remote CI record; actual GitHub Actions runs are authoritative for remote results.

如果要从无远程地址的本地副本另建新仓库，可使用附带脚本并显式指定新名称；它不会覆盖现有仓库或替换已有 `origin`。
To create a separate repository from a local copy with no remote, use the supplied script with an explicit new name; it will not overwrite an existing repository or replace an existing `origin`.

```bash
bash scripts/publish_github.sh YourGitHubName/YourNewRepository private
```

新建仓库脚本需要已安装并登录的 GitHub CLI；当前仓库已经存在，无需运行该脚本。
The repository-creation script requires an installed, authenticated GitHub CLI; it is unnecessary for this already existing repository.
