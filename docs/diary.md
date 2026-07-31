# 本地 Embedding 环境变量永久配置

如果本地 embedding 服务没有 API key，可以把 key 写成 `EMPTY`。在 PowerShell 中执行下面三条命令，把配置永久写入当前用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_BASE_URL", "你的_embedding_url", "User")
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_MODEL", "你的_embedding_model_name", "User")
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_API_KEY", "EMPTY", "User")
```

示例：

```powershell
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_BASE_URL", "http://localhost:8000/v1", "User")
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_MODEL", "bge-m3", "User")
[Environment]::SetEnvironmentVariable("ADARUBRIC_EMBEDDING_API_KEY", "EMPTY", "User")
```

设置完成后需要重启 PowerShell 或终端，再检查是否生效：

```powershell
echo $env:ADARUBRIC_EMBEDDING_BASE_URL
echo $env:ADARUBRIC_EMBEDDING_MODEL
echo $env:ADARUBRIC_EMBEDDING_API_KEY
```

如果想让当前 PowerShell 立即生效，也可以临时执行：

```powershell
$env:ADARUBRIC_EMBEDDING_BASE_URL="你的_embedding_url"
$env:ADARUBRIC_EMBEDDING_MODEL="你的_embedding_model_name"
$env:ADARUBRIC_EMBEDDING_API_KEY="EMPTY"
```
