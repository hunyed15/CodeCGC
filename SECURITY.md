# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | Yes                |
| < 1.0   | No                 |

## Reporting a Vulnerability

If you discover a security vulnerability in CodeCGC, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please send an email to the maintainers with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

### Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Fix release**: Depending on severity

## Security Measures

CodeCGC implements the following security measures:

### Input Validation

- **Path traversal prevention**: `validateSlug()` and `assertWithinRoot()` prevent directory escaping
- **Step path validation**: `validateStepPaths()` rejects absolute paths and `..` traversal
- **Input size limits**: Max 5000 chars per string, 100 items per array, 10 nesting depth

### Process Isolation

- **CLI sandboxing**: External CLIs run in restricted sandbox modes
- **Worker threads**: Long-running operations run in isolated workers
- **Process tree cleanup**: `taskkill` used to kill process trees on timeout

### YAML Safety

- **Safe schema**: All YAML parsing uses `JSON_SCHEMA` to reject dangerous tags (`!!js/function`)
- **Explicit validation**: `executor-config.ts` uses `parseYaml()` from `shared/yaml.ts`

### File System Protection

- **Workflow locks**: `.lock` files prevent concurrent write conflicts
- **Audit trails**: All operations logged to `.codecgc/` directory
- **Project root enforcement**: All paths resolved relative to project root

### Network Security

- **HTTP service binding**: CLI HTTP services only listen on `127.0.0.1`
- **No external network**: MCP servers operate locally, no external API calls by default

## Threat Model

### In Scope

- Path traversal attacks via malicious slugs or paths
- YAML deserialization attacks
- Process injection via CLI arguments
- Concurrent workflow corruption
- Denial of service via large inputs

### Out of Scope

- Social engineering attacks
- Physical access to development machine
- Vulnerabilities in external CLI tools (Codex, Gemini, OpenCode)
- Supply chain attacks on npm dependencies

## Security Best Practices for Users

1. **Keep dependencies updated**: Run `npm audit` regularly
2. **Validate inputs**: Don't pass untrusted data to MCP tools
3. **Review workflow changes**: Check `.codecgc/` directory for unexpected files
4. **Use sandboxing**: Keep CLI sandbox modes enabled
5. **Monitor audit logs**: Review audit files in `.codecgc/features/*/audits/`
