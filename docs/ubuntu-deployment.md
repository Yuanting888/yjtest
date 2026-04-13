# Ubuntu Deployment Guide

This guide is for deploying YJTest on Ubuntu 22.04 or 24.04 with Docker.

## 1. Install Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
```

## 2. Clone The Repository

```bash
git clone https://github.com/banlinhuang-sketch/YJautotest.git
cd YJautotest
cp .env.example .env
```

## 3. Update Production Environment Variables

Edit `.env` and update at least these values:

```env
DJANGO_SECRET_KEY=replace-with-a-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,server-ip
DJANGO_CORS_ALLOWED_ORIGINS=https://your-domain.com,http://server-ip:8913
DJANGO_ADMIN_PASSWORD=replace-with-a-strong-password
POSTGRES_PASSWORD=replace-with-a-strong-password
YJTEST_API_KEY=replace-with-a-new-api-key
```

If you only access the system by IP, replace `your-domain.com` with the server IP.

## 4. Start The Services

If you want to deploy the exact code from this repository, use local build mode:

```bash
chmod +x run_compose.sh
./run_compose.sh local
```

If you want faster startup and are okay with the upstream prebuilt images, use:

```bash
./run_compose.sh remote
```

## 5. Verify The Deployment

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

Default service ports:

- Frontend: `8913`
- Backend API: `8912`
- MCP: `8914`
- Playwright MCP: `8916`
- Qdrant: `8918`
- PostgreSQL: `8919`

Open the frontend in your browser:

```text
http://your-server-ip:8913
```

## 6. Firewall Recommendation

If you use `ufw`, only open the frontend port first:

```bash
sudo ufw allow 8913/tcp
sudo ufw enable
```

Avoid exposing `8912`, `8914`, `8916`, `8918`, and `8919` directly to the public Internet unless you have an explicit protection layer in front of them.

## 7. Common Commands

```bash
docker compose down
docker compose up -d
docker compose restart backend
docker compose logs -f
```

## 8. Notes

- `docker-compose.yml` is now production-oriented and respects `DJANGO_DEBUG` from `.env`.
- `docker-compose.local.yml` keeps a development-friendly default with `DJANGO_DEBUG=True`.
- After the first login, replace the default API key in the admin panel for production use.
