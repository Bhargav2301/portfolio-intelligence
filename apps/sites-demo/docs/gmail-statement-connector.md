# Gmail wealth-manager statement connector

Last verified: 2 September 2026

The Sites application can ask each authenticated user for the exact wealth-manager
sender address, obtain separate Google consent, and stage matching PDF or spreadsheet
attachments in the private `DOCUMENTS` R2 bucket. Imported files remain
`needs_review`; they do not change holdings or become trusted evidence automatically.

## Production environment

Configure these server-side Sites variables. Never prefix them with `NEXT_PUBLIC_`.

| Variable | Protection | Value |
|---|---|---|
| `GOOGLE_CLIENT_ID` | normal server configuration | Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | protected secret | Google OAuth web client secret |
| `GOOGLE_REDIRECT_URI` | normal server configuration | `https://portfolio-intelligence.satoshinara.chatgpt.site/api/connections/google/callback` |
| `CONNECTOR_ENCRYPTION_KEY` | protected secret | At least 32 cryptographically random bytes, stored as Base64 or hex |

The deployment also needs the `.openai/hosting.json` R2 binding named `DOCUMENTS`.

Generate the encryption key locally without printing it:

```powershell
$bytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$secret = [Convert]::ToBase64String($bytes)
Set-Clipboard -Value $secret
Remove-Variable bytes,secret
```

Paste the clipboard value into the protected Sites secret, save the environment
revision, then clear the clipboard with `Set-Clipboard -Value ''`.

## Google Cloud setup

1. Create or select a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen and its privacy/contact details.
3. Create an OAuth 2.0 Client ID of type **Web application**.
4. Add the exact production redirect URI shown above. Do not add a wildcard.
5. Add the owner account as a test user while the app remains in testing.
6. Store the client ID and client secret in Sites, save a new environment revision,
   and privately redeploy the saved Site version.
7. Sign in to Portfolio Intelligence, save the exact wealth-manager sender address,
   open **Accounts**, and select **Connect Google**.
8. Review the Google consent screen before approving read-only Gmail access.
9. Back in **Accounts**, select **Import matching files**. The query is restricted to
   the saved sender, supported attachment types, and the most recent 18 months.

The connector requests `https://www.googleapis.com/auth/gmail.readonly`. Google
classifies Gmail read scopes as restricted. Before any broad production launch,
complete the applicable OAuth verification, privacy-policy, data-retention, and
security-assessment requirements. Keep this owner-only deployment in test mode until
those gates are complete.

## Safety boundary

- Maximum 30 matching messages per sync and 20 MB per attachment.
- Supported types: PDF, CSV, TSV, XLS, and XLSX.
- OAuth access and refresh tokens are encrypted with AES-GCM before D1 storage.
- Raw attachments are private R2 objects; D1 stores only metadata and storage keys.
- Deleting account data removes mailbox tokens, import metadata, and matching private
  objects.
- The connector does not send email, modify Gmail, or place trades.

## Official references

- [Google OAuth 2.0 for web-server applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail API REST reference](https://developers.google.com/workspace/gmail/api/reference/rest)
