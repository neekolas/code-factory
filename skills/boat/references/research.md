# Research: Boat with a local subscription gateway

Checked 2026-10-28. This is an implementation brief, not a provider endorsement.

## Architecture and tradeoffs

The agent runs in a Boat VM. Its inference requests go over private Tailscale
HTTPS to CLIProxyAPI on the user's Mac. CLIProxyAPI keeps and refreshes the two
Claude logins and one Codex login, then connects to each provider from the Mac.
The VM receives only a gateway client key and a transient enrollment key. The
gateway key is stored in the worker's native client configuration, protected by
file permissions. Worker snapshots therefore remain sensitive even though no
subscription OAuth tokens leave the Mac.

This achieves local inference egress without routing the entire VM through a
Tailscale exit node. Git, package downloads, and other VM traffic still use the
VM network. The Mac is a single point of failure: sleep, logout, updates, lost
internet, or proxy failure interrupt inference. Already running work and files
remain on Boat. Stop idle VMs to avoid compute use during an outage.

CLIProxyAPI advertises Claude/Codex OAuth, streaming, tool calls, multiple
accounts, and compatible APIs. Its source implements session affinity and
per-credential prefixes. Prefer Claude Code with Claude models and Codex with
Codex models; avoid protocol translation until tested for the needed tools.
Pooling is not a promise of additive limits, unlimited concurrency, or avoiding
provider restrictions.

Sources: [overview](https://help.router-for.me/introduction/what-is-cliproxyapi),
[configuration](https://help.router-for.me/configuration/options),
[source](https://github.com/router-for-me/CLIProxyAPI),
[Claude client](https://help.router-for.me/agent-client/claude-code),
[Codex client](https://help.router-for.me/agent-client/codex).

## Subscription support and uncertainty

Anthropic documents native Claude Code subscription use and distinguishes it
from third-party developers intermediating subscription credentials for users.
Its docs do not establish permission for this personal CLIProxyAPI deployment.
No primary source checked establishes that a residential IP makes subscription
proxying permitted or protects an account from restrictions. The user's concern
about data-center IPs is a motivation, not a verified diagnosis. If proxy use is
rejected, investigate the response; do not add fingerprint spoofing or retry
across accounts to work around an account enforcement decision.

OpenAI documents custom Codex providers and a separate Sign in with ChatGPT
integration. That does not establish official support for CLIProxyAPI's OAuth
flow. Test the actual selected model, tools, completion, and resumption. Treat
both providers' terms and endpoints as changeable.

Sources: [Anthropic authentication and credential use](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use),
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
[OpenAI's app-server integration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server).

## Why not Boat's own credential proxy?

Boat supports multiple accounts, profiles, and a proxy that keeps real keys out
of guests. That proxy egresses through Boat and does not satisfy the requested
Mac egress. It also chooses one active account per credential; profile switching
is distinct from CLIProxyAPI pooling. Its custom API configuration asks for a
public HTTPS URL, so it is not a substitute for joining guests to the private
tailnet. The inspected Boat token lacks `account.admin`, needed for profile
management. A normal browser login can manage environments. The worker
path uses a dedicated environment with only gateway client credentials; builders
use `--no-env`. The gateway client key is stored by Boat, but subscription OAuth
credentials remain local. Explicit approval is required for this transfer.

Sources: [Boat credentials](https://docs.boat.dev/ai-credentials),
[keys and subscriptions](https://docs.boat.dev/integrated-agents/keys).

## Lifecycle and verification

Boat has native prompt, events, conversation, steering, and interrupt commands.
Use those instead of inventing a second task queue. A single sandbox shares one
home directory and credential context across conversations. Snapshots include
home and system changes but exclude running processes and volatile runtime
state. Every clone therefore needs a new Tailscale identity and runtime key
injection. A base snapshot should contain dependencies and setup tools only.

The local installed Boat agent was inspected read-only. It does not map an
arbitrary `OPENAI_BASE_URL` into a custom Codex provider. An explicit
`model_providers.boat_proxy` configuration is required. This is an observed
implementation detail, not a permanent Boat API contract.

Live testing also found that Boat regenerates its agent service, dropping an
arbitrary systemd environment override. Its named-environment variables were
available in shells but not native agents. Configure the native client files
as the hub guide describes, using only the gateway key. Its model allowlist rejects account-prefixed names, even
when the proxy supports them. Native Boat tasks use the pooled unprefixed model
IDs; direct CLI/API clients can use explicit account routes.

Sources: [Boat CLI](https://docs.boat.dev/cli-reference),
[customization](https://docs.boat.dev/integrated-agents/customize),
[setup lifecycle](https://docs.boat.dev/setup),
[snapshot contents](https://docs.boat.dev/snapshots/whats-saved),
[Tailscale ephemeral nodes](https://tailscale.com/docs/features/ephemeral-nodes),
[auth keys](https://tailscale.com/docs/features/access-control/auth-keys).

Required acceptance checks: private network reachability; 401 without a proxy
key; 404 on management APIs; exactly two distinct Claude credentials and one
Codex credential stored locally; a real Claude task and Codex task via Boat;
events, steering and completed turns; a stopped/resumed worker that reconnects;
and a second clone with a distinct Tailscale node. Record which checks actually
passed in the session handoff rather than treating this checklist as evidence.

## User-supplied hub guide

Read in full: [t3dotgg's CLIProxyAPI hub guide](https://gist.github.com/t3dotgg/59a521d2ee8d70aaf90e280c175072af),
revision `14ad2748014e2d342534e04851df59dd10a360df`.
It supports the local-hub topology, loopback binding, OAuth on the hub, and
session affinity. Its experience with account restrictions is anecdotal, not
provider permission. Keep personal subscriptions for the user's own work and
use Claude Code for Claude subscription requests.

Differences and follow-ups:

- This deployment uses private HTTPS port 443; the guide uses 8317. Both can
  proxy to loopback 8317. No public Funnel is needed.
- The management API and panel stay disabled here. Remote quota dashboards are
  optional and would require separate protected management access.
- Enable Codex `supports_websockets` and verify a real native task before
  declaring that transport operational. The initial SSE test alone is not proof.
- The environment requests one-hour main-conversation caching with
  `CLAUDE_CODE_PROMPT_CACHE_TTL=1h`. Anthropic documents that this is a supported
  override on recent Claude Code versions and that a gateway must preserve the
  relevant `anthropic-beta` header. Measure cache creation/read counts in the
  real client; affinity alone does not prove cache effectiveness.
- Reset-aware account selection is a separate custom fork, not an upstream
  round-robin setting. It is not included in this implementation.
- Local checks found AC sleep disabled and no Tailscale exit node selected.
  The external IP-organization lookup was not authorized, so residential egress
  has not been independently verified with an IP lookup service.

Primary follow-up references:
[Claude prompt-cache controls](https://code.claude.com/docs/en/prompt-caching#choose-the-ttl-yourself),
[Codex provider configuration](https://learn.chatgpt.com/docs/config-file/config-reference).
