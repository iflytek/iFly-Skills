# 服务器与域名部署

本说明用于把 iFly-Skills 服务部署到自己的 Linux 服务器，提供 Coze 可以访问的 HTTPS 地址。部署方负责服务器、域名、证书及讯飞账号；插件调用者使用配置好的服务。

先选择运行方式：

- **Docker Compose**：按下面的步骤启动服务和 HTTPS 代理，适用于除 GIF 外的工具。
- **需要 GIF**：使用本文最后的 [Linux 直接运行方式](#启用-giflinux-直接运行)，由本机 Docker 运行 GIF 渲染。其余域名、证书和 Coze 配置相同。

## 准备服务器和账号

准备一台可访问公网的 Linux 服务器，建议至少 4 GiB 内存，并为镜像、任务和输出文件预留磁盘空间。后端容器限额为 2 GiB，临时文件最多占其中 1 GiB；系统、代理及可选 GIF 渲染还需要内存。安装 Git、Docker Engine、Docker Compose v2 和 Docker Buildx；运行 Docker 命令的账号需要相应权限。

将仓库放到服务器，进入仓库根目录并检查 Docker 安装：

```sh
git clone https://github.com/iflytek/iFly-Skills.git
cd iFly-Skills
docker version
docker compose version
docker buildx version
```

部署包含 `integrations/coze/` 的代码版本，并保留 `skills/` 目录。后续更新也使用这一份仓库。

在[讯飞控制台](https://console.xfyun.cn)注册账号，为要使用的能力开通服务、准备额度，取得 APPID、APIKey 和 APISecret。合同审核还需要独立配置对应的凭证及服务权限，详见[配置说明](../README.md#配置)。

## DNS、端口与 HTTPS

以下以 `coze.example.com` 为例，操作时替换为自己的域名。

1. 在域名提供商的 DNS 管理中新增 **A 记录**：主机记录填 `coze`，值填服务器的公网 IPv4 地址。等待生效后，从服务器外执行 `nslookup coze.example.com`，确认解析到正确地址。
2. 选择服务端口。本示例默认 **8443**，服务地址为 `https://coze.example.com:8443`。如果服务器的 443 端口可用，也可以使用 **443**，地址为 `https://coze.example.com`。
3. 在云服务器安全组和服务器防火墙中放行所选 TCP 端口。内部 8000 端口由部署配置使用，无需对外开放。
4. 为该域名申请公网信任的 HTTPS 证书，准备完整证书文件和私钥，通常为 `fullchain.pem`、`privkey.pem`。证书可从证书服务商或自己的证书管理工具获取。只有高端口可用时，可选择 **DNS 验证（DNS-01）**，按签发工具提示添加 `_acme-challenge.coze` TXT 记录及验证值。

DNS 只负责把域名指向服务器，端口要写在 URL 中。本示例加载准备好的证书；部署方需要在证书到期前续期，更新文件后重启 HTTPS 代理。

使用 IPv6 时，可按实际地址添加 AAAA 记录；使用已有网关时，可按其说明改用 CNAME。使用 CDN／DNS 代理时，先确认支持所选端口。一般服务器使用上述 A 记录即可。

## 准备配置与数据目录

部署使用两份配置文件：一份设置端口和部署目录，另一份设置 Coze 访问密钥及讯飞凭证。以下目录是示例，可以替换为自己的专用目录。

| 文件／目录 | 内容 |
| --- | --- |
| `integrations/coze/deploy/.env` | 域名、端口、部署目录和代码版本 |
| `/srv/ifly-coze/runtime.env` | 工作空间、服务密钥、启用能力和讯飞凭证 |
| `/srv/ifly-coze/data/` | 持久保存的任务及输出文件 |
| `/srv/ifly-coze/tls/` | HTTPS 证书和私钥 |

### 1. 设置部署地址

从仓库根目录复制示例：

```sh
cp integrations/coze/deploy/.env.example integrations/coze/deploy/.env
git rev-parse HEAD
```

编辑 `integrations/coze/deploy/.env`：

```dotenv
COZE_DEPLOY_DIR=/srv/ifly-coze
COZE_PUBLIC_HOST=coze.example.com
COZE_HTTPS_PORT=8443
COZE_SOURCE_REVISION=<上面命令返回的提交值>
COZE_IMAGE_TAG=local
```

`COZE_PUBLIC_HOST` 只填域名；`COZE_SOURCE_REVISION` 填实际提交值，不保留尖括号。使用 443 时修改端口值。`COZE_IMAGE_TAG` 是本次镜像的版本标签，更新时换成新的标签，便于保留旧版本。

### 2. 填写运行配置

创建专用目录并复制配置。命令中的 `10001` 是容器使用的账号编号，按示例保留：

```sh
sudo install -d -m 0700 /srv/ifly-coze
sudo install -d -o 10001 -g 10001 -m 0700 /srv/ifly-coze/data /srv/ifly-coze/tls
sudo install -o 10001 -g 10001 -m 0400 integrations/coze/.env.example /srv/ifly-coze/runtime.env
sudoedit /srv/ifly-coze/runtime.env
```

按[完整配置说明](../README.md#配置)填写运行配置，重点是以下内容：

| 配置项 | 填写方法 |
| --- | --- |
| `COZE_ENABLED_SITES` | 国内填 `cn`，国际填 `global`，两站填 `cn,global` |
| `COZE_<SITE>_WORKSPACE_ID` | 对应站点的工作空间 ID，可在空间页面 URL 中找到 |
| `COZE_<SITE>_BACKEND_API_KEY` | 自己生成的服务密钥；两站分别生成和填写 |
| `COZE_<SITE>_BACKEND_BASE_URL` | 实际服务地址，本例为 `https://coze.example.com:8443` |
| `COZE_<SITE>_ALLOWED_SKILLS` | 保留准备启用的 Skill ID，用逗号分隔；本 Compose 方式移除 `animated-sketch-diagram` |
| `IFLY_APP_ID`、`IFLY_API_KEY`、`IFLY_API_SECRET` | 从讯飞控制台取得的凭证 |
| `IFLY_CONTRACT_*` | 启用合同审核时填写对应的独立凭证 |
| `COZE_ARTIFACT_BASE_URL` | 音频、视频、报告等文件的下载地址，本例与服务地址相同 |

`<SITE>` 对应 `CN` 或 `GLOBAL`，只填写启用站点的配置。可运行 `openssl rand -hex 32` 生成一个服务密钥，两站启用时运行两次。平台 `API_TOKEN` 可留空。此方式下 `COZE_RENDER_IMAGE` 留空，`COZE_DATA_DIR` 由 Compose 设置。

### 3. 放置证书

将下面的来源路径替换为自己的证书和私钥路径，再执行：

```sh
sudo install -o 10001 -g 10001 -m 0400 /path/to/fullchain.pem /srv/ifly-coze/tls/fullchain.pem
sudo install -o 10001 -g 10001 -m 0400 /path/to/privkey.pem /srv/ifly-coze/tls/privkey.pem
```

凭证和私钥保留在服务器上，配置文件及 `data/` 目录不公开、不提交到仓库。

## 构建、启动与检查

按顺序执行。`-p ifly-coze` 为本次部署命名；同一服务器部署多份时使用不同名称、端口和目录。

```sh
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml config --quiet
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml build
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml run --rm --no-deps --interactive=false -T proxy caddy validate --config /etc/caddy/Caddyfile
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml up -d
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml ps
```

前两项检查配置并构建镜像，第三项检查 HTTPS 代理配置，最后两项启动并查看服务状态。确认后端为健康状态、代理正常运行。

从服务器外访问服务，使用自己的地址：

```sh
curl --fail https://coze.example.com:8443/healthz
```

正常返回 `{"status":"ok"}`。再在自己的管理电脑上按[安装与启动说明](../README.md#安装与启动)安装依赖，准备 `integrations/coze/.env`，填入与服务器一致的本站服务地址、工作空间、密钥和启用能力。从管理电脑的仓库根目录执行已启用站点的检查：

```sh
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_deployment.py --site cn --all-tools
uv run --locked --project integrations/coze --python 3.13 python -B integrations/coze/scripts/check_deployment.py --site global --all-tools
```

配置另存时添加 `--env-file <配置文件路径>`。结果中的 `passed` 应为 `true`。检查会验证 HTTPS、密钥和已启用工具的路由，并读取内置发音人列表，不消耗讯飞额度。检查直接连接服务，不使用本机代理。

检查通过说明服务地址、认证和路由可用，不代表讯飞权限／额度或 GIF 环境已验证。按[插件接入与发布说明](../PUBLISHING.md)导出插件文件，在 Coze 中导入并使用真实样本调试。

示例代理等待后端响应的上限为 660 秒，覆盖媒体操作的 600 秒预算。Coze 节点和额外网关仍有各自超时，需要按实际调用耗时配置。普通调用的后端预算仍为 60 秒。

## 运行与更新

每个数据目录运行一个后端服务。输出文件默认保留 1 小时，供讯飞拉取的视频和训练录音保留 24 小时；任务和去重记录持续保存。定期检查磁盘空间和证书到期时间。

以下命令仍从仓库根目录执行：

```sh
# 查看本部署的状态和日志
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml ps
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml logs --tail 100

# 运行配置变更后，重启后端
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml restart backend

# 更换证书后，重启 HTTPS 代理
docker compose -p ifly-coze --env-file integrations/coze/deploy/.env -f integrations/coze/deploy/compose.yaml restart proxy
```

备份时先用相同的 Compose 命令执行 `stop backend`，备份 `/srv/ifly-coze/data/` 后执行 `start backend`。运行配置和证书也应单独妥善保存。

更新代码前记录当前提交和镜像标签，保留旧镜像；停止后端，切换到新代码，填写新的 `COZE_SOURCE_REVISION` 和 `COZE_IMAGE_TAG`，再执行上面的构建、启动和检查。回退时恢复旧代码及标签，使用原数据目录启动并检查。接口有变更时，同步更新 Coze 插件，见[发布说明](../PUBLISHING.md#工作空间发布与更新)。

关闭本部署时使用相同的 Compose 命令执行 `down`，配置和数据目录会保留。

## 常见问题

| 现象 | 先检查什么 |
| --- | --- |
| 域名解析错误 | A 记录是否指向公网 IP；可选 AAAA 是否正确 |
| 连接超时 | URL 中的端口、安全组、防火墙和代理是否正常 |
| 证书错误 | 域名是否匹配，证书是否完整、过期；更换后是否重启代理 |
| `401` | Coze 中的 `X-API-Key` 是否与本站运行配置一致 |
| `403` | 所调用 Skill 是否在本站 `ALLOWED_SKILLS` 中 |
| `404` | 服务地址和工具路径是否正确；使用路径前缀时是否一致 |
| `DEPENDENCY_UNAVAILABLE` | 讯飞凭证、文件下载地址及所需运行环境是否已配置 |
| 讯飞权限／额度错误 | 讯飞应用是否开通了具体能力，额度是否充足 |

## 路径前缀与文件结果

示例直接使用域名根路径。需要 `https://coze.example.com:8443/coze` 这样的地址时，在 `Caddyfile` 站点块内，将原 `reverse_proxy` 块替换为：

```caddyfile
handle_path /coze/* {
    reverse_proxy backend:8000 {
        transport http {
            dial_timeout 5s
            response_header_timeout 660s
        }
    }
}
handle {
    respond "Not found" 404
}
```

其余 TLS、日志及超时配置保留。后端地址和 `COZE_ARTIFACT_BASE_URL` 均填包含 `/coze` 的 URL，重新校验配置并重启代理，再检查服务。Linux 直接运行时，代理目标改为 `127.0.0.1:8000`。

音频、视频、GIF 和报告通过服务返回的限时链接下载，`data/` 只用于服务器保存数据。持有链接即可在有效期内下载文件，应妥善保管这些地址。

## 启用 GIF：Linux 直接运行

需要 GIF 时，后端直接运行在 Linux 上，GIF 由本机 Docker 渲染。准备本机 Docker Engine、Docker 命令、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 HTTPS 代理。服务账号需要 Docker 权限，等同于管理主机，应在自己管理的服务器上使用。

以下示例使用 `/opt/iFly-Skills` 存放仓库，`/srv/ifly-coze-native` 存放配置和数据。由服务器管理员操作，并选择此方式作为唯一后端。

### 1. 安装并配置服务

将仓库放到 `/opt/iFly-Skills`，从该仓库根目录执行：

```sh
UV_PYTHON_INSTALL_DIR=/opt/ifly-coze-python uv python install 3.13
UV_PYTHON_INSTALL_DIR=/opt/ifly-coze-python uv sync --locked --project integrations/coze --python 3.13
docker buildx build --load -f integrations/coze/deploy/render/Dockerfile -t ifly-coze-render .
docker image inspect --format '{{.Id}}' ifly-coze-render
```

保存最后一项返回的完整 `sha256:...` 值，稍后填入渲染配置。管理员需有权写入这些 `/opt` 目录，服务账号也需要能读取仓库及 Python 环境。

创建专用服务账号和目录；已有同名账号时复用：

```sh
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin ifly-coze
sudo install -d -o root -g ifly-coze -m 0750 /srv/ifly-coze-native
sudo install -d -o ifly-coze -g ifly-coze -m 0700 /srv/ifly-coze-native/data
sudo install -o root -g ifly-coze -m 0640 integrations/coze/.env.example /srv/ifly-coze-native/runtime.env
sudoedit /srv/ifly-coze-native/runtime.env
```

按前面的运行配置表填写工作空间、密钥、能力、讯飞凭证和 HTTPS 地址，并设置：

- `COZE_DATA_DIR=/srv/ifly-coze-native/data`
- `COZE_RENDER_IMAGE`：填上面的完整镜像 ID。
- 本站 `ALLOWED_SKILLS`：加入 `animated-sketch-diagram`。

### 2. 启动并设置开机运行

将以下内容保存为 `/etc/systemd/system/ifly-coze.service`。如果仓库或数据目录不同，修改对应路径；systemd 用于后台运行和开机启动：

```ini
[Unit]
Description=iFly-Skills Coze backend
Requires=docker.service
After=network-online.target docker.service
Wants=network-online.target

[Service]
User=ifly-coze
Group=ifly-coze
SupplementaryGroups=docker
WorkingDirectory=/opt/iFly-Skills/integrations/coze
Environment=COZE_ENV_FILE=/srv/ifly-coze-native/runtime.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/iFly-Skills/integrations/coze/.venv/bin/python -B -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --no-proxy-headers --timeout-graceful-shutdown 30
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/srv/ifly-coze-native/data

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now ifly-coze.service
sudo systemctl status ifly-coze.service
```

### 3. 配置 HTTPS 并检查 GIF

使用自己的 HTTPS 代理，将请求转发到 `127.0.0.1:8000`。使用 Caddy 时，沿用本目录 `Caddyfile` 的全局日志和超时配置，站点块可以填写为：

```caddyfile
https://coze.example.com {
    tls /path/to/fullchain.pem /path/to/privkey.pem
    request_body {
        max_size 2MB
    }
    reverse_proxy 127.0.0.1:8000 {
        transport http {
            response_header_timeout 660s
        }
    }
}
```

这里使用 443；使用高端口时在域名后写上端口，并同步填写服务和文件下载地址。替换证书路径，确认代理账号能读取证书。按代理自己的启动方式启动并设置开机运行。

按前面的检查步骤确认 HTTPS 和工具路由，再用 `render_html_to_gif → get_render` 完成一次 GIF 生成、查询和下载，检查尺寸及动画。调试方法见[发布说明](../PUBLISHING.md#调试工具)。

配置或代码更新后执行 `sudo systemctl restart ifly-coze.service` 并重新检查。备份数据前先停止该服务，备份完成后再启动。各工具仍需按实际讯飞账号确认权限和额度。
