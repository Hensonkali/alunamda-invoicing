# ALUNAMDA Invoicing - Cloud Deployment

## Oracle Cloud Free Tier (Always Free VPS)

### Prerequisites
- Oracle Cloud account (free): https://cloud.oracle.com
- A domain name (optional but recommended for HTTPS)

---

## Step 1: Create Oracle Cloud VM

1. Log in to Oracle Cloud Console
2. Go to **Compute > Instances > Create Instance**
3. Settings:
   - **Name:** alunamda
   - **Image:** Ubuntu 22.04 (or Oracle Linux 9)
   - **Shape:** VM.Standard.A1.Flex (ARM - always free)
   - **OCPU count:** 4
   - **Memory:** 24 GB
   - **Boot volume:** 200 GB
4. **Add SSH keys** (generate with `ssh-keygen` on your local machine)
5. **Create** and wait 2-3 minutes
6. Note the **Public IP address**

---

## Step 2: Connect to your VPS

```bash
ssh ubuntu@YOUR_PUBLIC_IP
```

---

## Step 3: Run setup script

```bash
# Download the setup script (from your local machine, upload it)
scp scripts/setup-server.sh ubuntu@YOUR_PUBLIC_IP:~/

# On the VPS:
chmod +x setup-server.sh
./setup-server.sh
```

---

## Step 4: Upload the app

From your **local machine** (the `alunamda-cloud` folder):

```bash
# Upload entire project to VPS
scp -r ./* ubuntu@YOUR_PUBLIC_IP:/opt/alunamda/
```

---

## Step 5: Configure environment

On the VPS:

```bash
cd /opt/alunamda

# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Create .env file
cp .env.example .env
nano .env
```

Fill in:
- `SECRET_KEY` = the generated random string
- `BASE_URL` = your domain or IP (e.g., `https://invoicing.yourdomain.com`)

---

## Step 6: Configure domain (optional)

Edit `Caddyfile`:
```bash
nano Caddyfile
```

Replace `yourdomain.com` with your actual domain.

**If using a domain**, point DNS to your VPS IP:
- A record: `invoicing` → `YOUR_PUBLIC_IP`
- Or CNAME: `invoicing` → `YOUR_PUBLIC_IP`

---

## Step 7: Start the app

```bash
cd /opt/alunamda
docker compose up -d
```

First build takes 3-5 minutes. After that, it starts in seconds.

---

## Step 8: Verify

```bash
# Check containers are running
docker compose ps

# Check health
curl http://localhost:1111/api/health

# View logs
docker compose logs -f
```

Open in browser: `https://yourdomain.com` or `http://YOUR_PUBLIC_IP`

Login: `admin@alunamda.co.za` / `Admin@123`

---

## Managing the app

```bash
cd /opt/alunamda

# Stop
docker compose down

# Restart
docker compose restart

# Update (after code changes)
docker compose up -d --build

# View logs
docker compose logs -f app

# Backup database
docker compose exec app python -c "import asyncio; from database import _run_backup; _run_backup()"
```

---

## Backups

The app creates automatic backups on every startup (kept in `db/backups/` inside the container).

For manual backups:
```bash
# Backup to local machine
docker compose cp app:/app/db/alunamda.db ./backup-$(date +%Y%m%d).db

# Restore from backup
docker compose cp ./backup-20260101.db app:/app/db/alunamda.db
docker compose restart app
```

---

## Troubleshooting

**Container won't start:**
```bash
docker compose logs app
```

**Database locked:**
```bash
docker compose restart app
```

**Can't connect externally:**
```bash
# Check Oracle Cloud security list
# Go to: Networking > Virtual Cloud Networks > your VCN > Subnet
# > Security Lists > Default Security List
# Add Ingress Rules:
#   Source: 0.0.0.0/0
#   Destination Port: 80, 443
```

**Out of memory:**
```bash
# Check usage
docker stats

# If needed, reduce workers in Dockerfile:
# Change --workers 2 to --workers 1
```

---

## Cost

- **VM:** $0/month (Always Free tier)
- **Storage:** $0/month (200GB included free)
- **Bandwidth:** $0/month (10TB/month free)
- **Domain:** ~$10/year (optional)
- **Total: $0/month**
