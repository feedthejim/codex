# Codex SSO manual test harness

Everything needed to manually test Codex authentication before a release: an
**authentik** OIDC identity provider, a **tinyauth** forward-auth gateway, and
the local **nginx** reverse proxy that was already here for subpath testing.

Every credential in this directory is public throwaway test data.

> **Why authentik and not Authelia?** Authelia refuses to serve OIDC over plain
> HTTP, which would force self-signed-TLS trust into Codex's discovery/token
> fetches. authentik runs happily on http://localhost and also supports
> RP-initiated logout, so it exercises every Codex OIDC feature. tinyauth is not
> an OIDC provider — it tests the Remote-User forward-auth path instead.

## Pieces

| Piece            | Where                                                          | URL                     |
| ---------------- | -------------------------------------------------------------- | ----------------------- |
| authentik        | `compose.yaml`                                                 | <http://localhost:9010> |
| tinyauth         | `compose.yaml`                                                 | <http://localhost:3232> |
| nginx plain      | `server.conf` (existing)                                       | <http://localhost:8080> |
| nginx gated      | `forwardauth.conf` (tinyauth)                                  | <http://localhost:8081> |
| authentik config | `authentik/blueprints/codex-test.yaml` (applied automatically) |

Test identities (all passwords `insecure-test-password` unless noted):

| Account     | Where     | Groups                | Notes                          |
| ----------- | --------- | --------------------- | ------------------------------ |
| `akadmin`   | authentik | —                     | password `admin`; authentik UI |
| `testuser`  | authentik | readers               | ordinary OIDC login            |
| `testadmin` | authentik | readers, codex-admins | for admin-group mapping        |
| `test`      | tinyauth  | —                     | forward-auth login             |

## Start everything

```sh
# 1. The identity providers (first start pulls images; authentik takes
#    a minute or two to migrate + apply the blueprint).
docker compose -f test-proxy/compose.yaml up -d

# 2. Codex, as usual (the harness assumes url_path_prefix = "/codex").
make dev

# 3. The reverse proxy (plain on 8080, tinyauth-gated on 8081).
make dev-reverse-proxy
```

Sanity checks:

```sh
curl -s http://localhost:9010/application/o/codex-test/.well-known/openid-configuration | head -c 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3232/api/auth/nginx   # 401
```

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

2. Browse <http://localhost:8081/codex/> → redirected to the tinyauth login →
   sign in `test` / `insecure-test-password` → back in Codex, logged in as
   `test` (auto-created).
3. **Gating:** confirm <http://localhost:8081/codex/opds/v1.2/r/0/1> and the
   WebSocket (`/codex/api/v4/ws`, watch devtools) also bounce to login when
   logged out of tinyauth.
4. **Spoof-proofing (gated port):**

    ```sh
    curl -s -o /dev/null -w '%{http_code}\n' \
      -H "Remote-User: admin" http://localhost:8081/codex/api/v4/session
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

## Reset

```sh
docker compose -f test-proxy/compose.yaml down -v   # wipe IdP state
```

Codex-side cleanup between runs: delete the auto-created users (`testuser`,
`testadmin`, `test`) in Admin → Users, and disable OIDC in the Auth tab (or
restore your config dir from backup).
