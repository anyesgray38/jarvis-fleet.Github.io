# AEGIS Control Center

Production web control plane for AEGIS Fleet. The UI is intentionally separate from the Python execution plane and contains no credentials or direct Tailscale access.

## Run

`npm install && npm run dev`

## Deploy

Configure Vercel with the repository root directory set to `web`, framework preset `Next.js`, and build command `npm run build`.