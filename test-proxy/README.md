# Codex SSO manual test harness

Everything needed to manually test Codex authentication before a release: an
**authentik** OIDC identity provider, a **tinyauth** forward-auth gateway, and
an **nginx** reverse proxy — all as `docker compose` services. Only Codex itself
runs on the host (`make dev`).

Every credential in this directory is public throwaway test data.

> **Why authentik and not Authelia?** Authelia refuses to serve OIDC over plain
> HTTP, which would force self-signed-TLS trust into Codex's discovery/token
> fetches. authentik runs happily on http://localhost and also supports
> RP-initiated logout, so it exercises every Codex OIDC feature. tinyauth is not
> an OIDC provider — it tests the Remote-User forward-auth path instead.

## Pieces

| Piece            | Where                                                          | URL                                 |
| ---------------- | -------------------------------------------------------------- | ----------------------------------- |
| authentik        | `compose.yaml`                                                 | <http://localhost:9010>             |
| tinyauth         | `compose.yaml`                                                 | <http://tinyauth.localtest.me:3232> |
| nginx plain      | `compose.yaml` + `server.conf`                                 | <http://localhost:8080>             |
| nginx gated      | `compose.yaml` + `forwardauth.conf`                            | <http://codex.localtest.me:8081>    |
| authentik config | `authentik/blueprints/codex-test.yaml` (applied automatically) |

`*.localtest.me` all resolve to `127.0.0.1` via public DNS — used for the
tinyauth path because tinyauth v5 refuses to run on a bare `localhost` app URL
(it sets its session cookie for a parent domain). Everything else stays on
`localhost`.

The nginx service and `bin/run-test-proxy.sh` (native) share `server.conf` and
`forwardauth.conf`; only the backend addresses differ (`upstreams-docker.conf`
vs `upstreams-native.conf`).

Test identities (all passwords `insecure-test-password` unless noted):

| Account     | Where     | Groups                | Notes                          |
| ----------- | --------- | --------------------- | ------------------------------ |
| `akadmin`   | authentik | —                     | password `admin`; authentik UI |
| `testuser`  | authentik | readers               | ordinary OIDC login            |
| `testadmin` | authentik | readers, codex-admins | for admin-group mapping        |
| `test`      | tinyauth  | —                     | forward-auth login             |

## Start everything

```sh
# 1. The whole harness — authentik, tinyauth, AND nginx (plain on 8080,
#    tinyauth-gated on 8081). First start pulls images; authentik takes a
#    minute or two to migrate + apply the blueprint.
docker compose -f test-proxy/compose.yaml up -d

# 2. Codex, as usual (the harness assumes url_path_prefix = "/codex").
#    nginx reaches it on the host via host.docker.internal.
make dev
```

Sanity checks:

```sh
curl -s http://localhost:9010/application/o/codex-test/.well-known/openid-configuration | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' http://tinyauth.localtest.me:3232/api/auth/nginx  # 401
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/codex/                       # Codex via nginx
```

> **Native nginx alternative.** If you'd rather run nginx on the host (e.g. to
> also exercise the 8443 TLS/HTTP3 listeners the container path omits), skip the
> `nginx` service and run `make dev-reverse-proxy` instead — it uses the same
> `server.conf` / `forwardauth.conf` with localhost backends. Either comment out
> the `nginx` service or
> `docker compose ... up -d authentik-server authentik-worker tinyauth postgresql redis`
> to avoid the 8080/8081 port clash.

## Test 1 — native OIDC login (authentik)

1. Browse <http://localhost:8080/codex/>, log in as your local admin, open
   **Admin → Auth**, expand **OIDC Single Sign-On**, and enter:
    - Provider Name: `Authentik`
    - Server URL: `http://localhost:9010/application/o/codex-test/`
    - Client ID: `codex-test`
    - Client Secret: `insecure-codex-test-secret`
    - (scope stays `openid profile email` — authentik ships groups in the
      profile scope)
2. **Test Connection** → expect issuer + authorization/token/userinfo ✓ and
   end-session ✓.
3. Enable OIDC, save, log out.
4. The lock screen / login dialog now shows **Login with Authentik**. Click it,
   sign in as `testuser`, land back in Codex logged in as `testuser` (check
   Admin → Users: the account was auto-created).
5. **Group sync:** create a Codex group named `readers` (Admin → Groups), turn
   on _Sync Groups_ in the Auth tab, log in as `testuser` again → the user is in
   `readers`. Groups that don't exist in Codex (`codex-admins` before you create
   it) are ignored, never created.
6. **Admin group:** set _Admin Group_ to `codex-admins`, log in as `testadmin` →
   account gets staff+superuser; remove `testadmin` from the group in authentik
   (or change _Admin Group_) and log in again → revoked.
7. **RP-initiated logout:** enable _Also Log Out of the Identity Provider_, log
   in via SSO, then log out of Codex → you land on authentik's end-session page
   and the authentik session is gone.
8. **Linking:** in authentik create a user whose username matches an existing
   local Codex user; SSO login links to (not duplicates) it — including the
   admin account, per the documented trust model.
9. **Error page:** stop the compose stack and click the SSO button →
   `/auth/sso-error` shows the human-readable failure, not a stack trace.
10. **Disabled = 404:** turn OIDC off, then
    `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/codex/sso/oidc/login/`
    → `404`.

## Test 2 — tinyauth forward-auth (Remote-User)

1. Restart Codex with header auth enabled:

    ```sh
    CODEX_AUTH_REMOTE_USER=1 make dev
    ```

2. Browse <http://codex.localtest.me:8081/codex/> → redirected to the tinyauth
   login (`tinyauth.localtest.me:3232`) → sign in `test` /
   `insecure-test-password` → back in Codex, logged in as `test` (auto-created).
3. **Gating:** confirm <http://codex.localtest.me:8081/codex/opds/v1.2/r/0/1>
   and the WebSocket (`/codex/api/v4/ws`, watch devtools) also bounce to login
   when logged out of tinyauth.
4. **Spoof-proofing (gated port):**

    ```sh
    curl -s -o /dev/null -w '%{http_code}\n' \
      -H "Remote-User: admin" http://codex.localtest.me:8081/codex/api/v4/session
    ```

    → `302` to the tinyauth login: the gate overrides the client header.

5. **The misconfiguration demo (ungated port):** the same curl against
   `http://localhost:8080/...` **authenticates as admin** — port 8080 does not
   strip `Remote-User`. This is exactly why the README warns to enable
   `CODEX_AUTH_REMOTE_USER` only when every route to Codex sets the header
   itself. Stop Codex and restart without the env var when done.
6. **Coexistence:** with both OIDC enabled and `CODEX_AUTH_REMOTE_USER=1`, both
   login paths work at once (8081 header-auths you; 8080 still offers the SSO
   button).

## Troubleshooting

**Vite HMR won't start / "port 5173".** The harness does not use 5173 — it
publishes only `9010`, `8080`, `8081`, and `3232` (check with
`docker compose -f test-proxy/compose.yaml config | grep published`). A blocked
Vite HMR is almost always a leftover `vite` from a previous `make dev` that
didn't exit cleanly:

```sh
lsof -i :5173         # find whatever holds 5173
pkill -f vite         # or kill the specific PID, then re-run make dev
```

**"address already in use" on 8080/8081.** The compose `nginx` service and the
native `make dev-reverse-proxy` both bind 8080/8081 — run one or the other, not
both.

**tinyauth restart loop: "invalid app url, must be at least second level
domain".** That's tinyauth v5 rejecting a bare `localhost` app URL. The current
`compose.yaml` uses `tinyauth.localtest.me` to satisfy it; if you still see
this, you're on an older copy — `git pull` / re-read `compose.yaml` and
`docker compose ... up -d --force-recreate tinyauth`.

## Reset

```sh
docker compose -f test-proxy/compose.yaml down -v   # wipe IdP state
```

Codex-side cleanup between runs: delete the auto-created users (`testuser`,
`testadmin`, `test`) in Admin → Users, and disable OIDC in the Auth tab (or
restore your config dir from backup).
