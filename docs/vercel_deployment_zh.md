# Vercel 离线演示部署

保留原审核预测器和本机 Streamlit 版，新增 `webapp.py` FastAPI 入口和 `public/` 网页。`pyproject.toml` 指定 `webapp:app`，避免 Vercel 把 Streamlit `app.py` 误当云端入口。公网只运行历史离线规则；v18 可展示扩充资料检索，但没有运行新的两轮模型，也没有新质量成绩。未能处理的条款显示 `model_needed`，不是已完成的预测。

## 账号中的部署设置

导入 `yoga-aaa/Singapore-rental-contract-review`。已有项目不必重建。在项目设置中核对：

| 设置 | 值 |
| --- | --- |
| Production Branch | `codex/project-foundation` |
| Root Directory | 仓库根目录 `.`，默认空白也表示根目录 |
| Framework Preset | FastAPI |
| Build Command | `python scripts/build_vercel.py`，或关闭人工 override 使用仓库配置 |
| Install Command | 保持框架默认，由 `pyproject.toml` 声明依赖 |
| Output Directory | 保持框架默认，不要填 `public` |
| Environment Variables | 不添加模型密钥，不上传 `.env` |

不要填 `data`、`src`、`public` 或 `app.py` 作为 Root Directory。不要把 Streamlit 启动命令作为构建命令。服务器固定 `live=False`，拒收付费和 key 字段；即使错误设置 `RENTAL_ENABLE_LIVE=1` 也不开放付费请求。模型 API 花费为零不等于托管服务永远免费；不自动升级托管计划。

推送新适配后，Git 集成通常会触发新构建。若没有触发，从 Deployments 新建部署，选择该分支最新提交。不要对旧 `6b50581` 再点 Redeploy，它仍缺少新入口。Git 历史重写会改变提交号，旧副本应重新 clone，不要合并旧历史再推送。

构建从原官方来源下载并校验两份模板，生成 135 个 CEA 小节；另下载七份官方网页，校验实质正文哈希并生成 49 个小节。全程不调用模型。参考文件在构建/函数环境中，不放入公开静态目录。如果网络不可达或正文变化，应保留失败保护，发回日志，不得删除哈希检查来通过构建。

## 成功后验收

1. 状态为 Ready，打开 Production 网站网址，而不是管理后台网址。
2. `/api/health` 显示 `status: ok`、`live_enabled: false`、`model_api_calls: 0`、135 个模板小节、49 个官方小节。
3. 内置五个例子依次为风险提示、有限通过、证据不足、私人住宅通知有限通过、`model_needed`。这是复用的功能自测，不是新泛化评测。
4. 下载合成 PDF，先确认无个人资料，再上传、检查片段、确认条件与例外，最后审核。查看引用原文和下载 JSON。切换输入应清掉旧结果。

输入发送到托管服务器，不发模型 API。应用不保存到磁盘，但托管基础设施可能留运维日志。个人资料识别不完整，不能上传真实合同。若不是 Ready，或出现 500/503，请给最新构建/函数日志和提交号。没有真正云端验收，就不能声称部署成功。

## 本机测试新版网页

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv\Scripts\python.exe scripts/build_vercel.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m uvicorn webapp:app --host 127.0.0.1 --port 8502 --no-access-log
```

新版网页是 `http://127.0.0.1:8502/`，原 Streamlit 是 `http://127.0.0.1:8501/`。两者仅限本机，不能当公网提交链接。浏览器自动化工具目前启动失败；HTTP 测试不能冒充视觉检查或云端验收。

`.gitignore`、`.vercelignore`、函数文件排除规则共同保护密钥、私人评测、提交包、稿件和视频。没有任意路径文件下载接口。稿件和原 Git 历史备份只在仓库外；清理不保证删除其他人旧副本或平台缓存。

技术依据：[Vercel Python 入口](https://vercel.com/docs/functions/runtimes/python)、[FastAPI 部署及构建命令](https://vercel.com/docs/frameworks/backend/fastapi)。
