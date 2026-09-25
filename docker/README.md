# piewall MCP server (read-only)

[piewall](https://piewall.th33raphat.dev) manages Windows Defender Firewall rules. This image runs
its [MCP](https://modelcontextprotocol.io) server in **file mode**: AI assistants can list, search
and analyse a set of firewall rules and find Block rules that override Allow rules.

It is **read-only by design**: a container cannot reach the Windows host's firewall, so it works on
a rules file you export on Windows. To let an assistant change the firewall, run the server on
Windows instead: `npx -y piewall-mcp` (see [the npm package](https://www.npmjs.com/package/piewall-mcp)).

Tools: `status`, `list_rules`, `rule_details`, `find_conflicts`.

Tags: `latest`, `<major>.<minor>`, `<version>`. Platforms: `linux/amd64`, `linux/arm64`.
Runs as a non-root user (uid 10001).

## 1. Export the rules on Windows

With [piewall](https://github.com/TheeraphatStudent/piewall/releases/latest) (reading needs no admin):

```powershell
piewall-cli export rules.json
```

The file holds every rule plus a snapshot of the programs listening on ports, which
`find_conflicts` uses. It describes your network setup: treat it as internal data.

## 2. Run the server

**stdio** (the default; what MCP clients launch):

```sh
podman run -i --rm -v ./rules.json:/data/rules.json:ro docker.io/th33raphat/piewall
docker run -i --rm -v "$PWD/rules.json:/data/rules.json:ro" th33raphat/piewall
```

On Windows use an absolute path, e.g. `-v C:\Users\me\rules.json:/data/rules.json:ro`.

**Streamable HTTP** at `http://localhost:8000/mcp`:

```sh
podman run --rm -p 127.0.0.1:8000:8000 -v ./rules.json:/data/rules.json:ro \
  -e PIEWALL_TRANSPORT=streamable-http -e PIEWALL_HOST=0.0.0.0 \
  docker.io/th33raphat/piewall
```

`PIEWALL_HOST=0.0.0.0` makes the server listen inside the container; `-p 127.0.0.1:8000:8000`
keeps it reachable from this machine only. The server accepts `Host: localhost`/`127.0.0.1` only
(DNS-rebinding protection); to reach it under another name add
`-e PIEWALL_ALLOWED_HOSTS=myhost:8000` (comma-separated). There is no authentication, so put a
reverse proxy with auth in front before exposing it to a network.

| Variable | Default | |
|---|---|---|
| `PIEWALL_RULES_FILE` | `/data/rules.json` | rules JSON made by `piewall export` |
| `PIEWALL_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `PIEWALL_HOST` | `127.0.0.1` | HTTP bind address |
| `PIEWALL_PORT` | `8000` | HTTP port (path `/mcp`) |
| `PIEWALL_ALLOWED_HOSTS` | | extra allowed `Host` headers, comma-separated |

## 3. Connect an MCP client

**Claude Code**

```sh
claude mcp add piewall -- podman run -i --rm -v /abs/path/rules.json:/data/rules.json:ro docker.io/th33raphat/piewall
# or, to a running HTTP container:
claude mcp add --transport http piewall http://localhost:8000/mcp
```

**Claude Desktop, Cursor** and other `mcpServers` JSON configs:

```json
{
  "mcpServers": {
    "piewall": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "/abs/path/rules.json:/data/rules.json:ro", "th33raphat/piewall"]
    }
  }
}
```

For HTTP, clients that support it take `{"url": "http://localhost:8000/mcp"}` instead.

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.piewall]
command = "podman"
args = ["run", "-i", "--rm", "-v", "/abs/path/rules.json:/data/rules.json:ro", "docker.io/th33raphat/piewall"]
```

Use absolute paths in client configs: clients start the command from their own working directory.

## Source and license

MIT. Source, issues and the `Containerfile`: <https://github.com/TheeraphatStudent/piewall>.
