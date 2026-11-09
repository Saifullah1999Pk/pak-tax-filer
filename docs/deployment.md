# Deployment (Google Cloud e2-micro VM)

The app runs on one free-tier VM with `docker-compose.prod.yml`: Postgres, the backend, and
Caddy, which serves the built frontend, forwards `/api` to the backend and gets HTTPS by itself.
Synthetic data only (README, non-negotiables): this is a demo, not a service for real documents.

## 1. Create the VM (once)

Google Cloud console → Compute Engine → VM instances → Create instance:

| Setting | Value |
|---|---|
| Region | us-central1, us-west1 or us-east1 (free tier) |
| Machine type | E2 → e2-micro |
| Boot disk | Ubuntu 24.04 LTS (x86/64), Standard persistent disk, 30 GB |
| Firewall | Allow HTTP and Allow HTTPS |

Set a budget alert first (Billing → Budgets & alerts). Note the VM's External IP, e.g.
`34.123.45.67`; the site's address is then `34-123-45-67.sslip.io` (sslip.io maps that name to
the IP, so no domain is needed).

## 2. Prepare the VM (once)

Open the VM's **SSH** button in the console, then:

```bash
# 2 GB of swap: the e2-micro has 1 GB of memory, not enough to build the frontend.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile
sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Docker, from Docker's own install script.
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Close the SSH window and open it again (so `docker` works without `sudo`), then:

```bash
# The code.
git clone https://github.com/Saifullah1999Pk/pak-tax-filer.git && cd pak-tax-filer
git switch 001-deployment
```

## 3. The server's secrets (once)

Create `.env` in `pak-tax-filer/` with `nano .env`. It is never committed:

```
SITE_ADDRESS=34-123-45-67.sslip.io
POSTGRES_PASSWORD=<a long random password: run `openssl rand -hex 24` and paste the output>
GEMINI_API_KEY=<your key from Google AI Studio>
```

Then `chmod 600 .env`, so only your user can read it.

## 4. Start it

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-user --email demo@example.com
```

The first build takes several minutes. Then open `https://34-123-45-67.sslip.io` and log in,
or choose **Create an account** (the `create-user` command is optional).

## 5. Private bucket for uploads (once; feature 003, FR-018)

Uploads go to a private Cloud Storage bucket instead of the VM's disk. The app reaches it with
the VM's own Google identity, so there is no key to create or store.

1. **Keep the IP:** stopping the VM can change its IP, and with it the site's address. VPC
   network → IP addresses → the VM's external address → **Promote to static IP address**. Check
   the price shown before confirming.
2. **Create the bucket:** Cloud Storage → Buckets → Create. A globally unique name (e.g.
   `pak-tax-filer-uploads-<something>`); location type **Region**, **us-central1** (free tier);
   storage class **Standard**; **Enforce public access prevention** ticked; access control
   **Uniform**. No other changes.
3. **Let the VM write to it:** Compute Engine → VM instances → `pak-tax-filer` → **Stop**. Then
   **Edit** → API and identity management → Access scopes → **Set access for each API** →
   Storage: **Read Write** → Save → **Start**.
4. On the VM, add `UPLOAD_BUCKET=<the bucket's name>` to `.env`, then start the app as in step 4.

Files uploaded before this stay on the disk volume and keep working.

## Updating

```bash
cd pak-tax-filer && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically when the backend starts.

## Checking on it

- `docker compose -f docker-compose.prod.yml ps`: all three services should be running.
- `docker compose -f docker-compose.prod.yml logs -f backend`: the backend's log.
- Stopping everything: `docker compose -f docker-compose.prod.yml down` (the data stays in its
  volumes; add `-v` only to delete it).
