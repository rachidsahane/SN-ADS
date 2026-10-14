#!/usr/bin/env bash
# start.sh : lance toute la démonstration Soro Nua Campaign Predictor en une commande.
#
#   ./start.sh          démarre tout (site, API, base de données, e-mails), charge les données,
#                       crée les comptes, entraîne et active un modèle, puis affiche l'adresse
#   ./start.sh stop     arrête tout (les données sont conservées)
#   ./start.sh reset    supprime les données locales puis refait tout à zéro
#
# Prérequis : Docker Desktop lancé, git, make. Première exécution : 10 à 15 minutes (construction).
set -euo pipefail
cd "$(dirname "$0")"

red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { red "Erreur : $*"; exit 1; }

action="${1:-start}"
case "$action" in start | stop | reset) ;; *) die "commande inconnue « $action » (utiliser : start, stop ou reset)" ;; esac

command -v docker > /dev/null 2>&1 || die "Docker n'est pas installé. Installer Docker Desktop : https://www.docker.com/products/docker-desktop/"
docker info > /dev/null 2>&1 || die "Docker ne répond pas. Lancer Docker Desktop, attendre qu'il soit prêt, puis relancer ./start.sh"
docker compose version > /dev/null 2>&1 || die "« docker compose » est introuvable. Mettre Docker Desktop à jour."
if ! command -v make > /dev/null 2>&1; then
  die "« make » est introuvable. Mac : lancer « xcode-select --install ». Linux : « sudo apt install make ». Windows : utiliser WSL (Ubuntu) ou Git Bash avec make."
fi

if [ "$action" = "stop" ]; then
  say "Arrêt de la démonstration (les données sont conservées)"
  make down
  exit 0
fi

if [ "$action" = "reset" ]; then
  say "Suppression des données locales"
  make clean
  rm -f .demo-accounts.txt
fi

# Mémoire donnée à Docker (la pile complète a besoin d'environ 6 Go).
mem_bytes="$(docker info --format '{{.MemTotal}}' 2> /dev/null || echo 0)"
if [ "${mem_bytes:-0}" -gt 0 ] && [ "$mem_bytes" -lt 5500000000 ]; then
  red "Attention : Docker dispose de $((mem_bytes / 1073741824)) Go de mémoire, il en faut au moins 6."
  red "Docker Desktop > Settings > Resources > Memory, puis relancer ./start.sh."
  exit 1
fi

# Ports : uniquement si la démonstration n'est pas déjà en marche (sinon ils sont forcément occupés par elle).
if [ -z "$(docker compose ps -q 2> /dev/null)" ]; then
  busy=""
  for port in 3000 8000 54321 54324; do
    if (echo > "/dev/tcp/127.0.0.1/$port") 2> /dev/null; then busy="$busy $port"; fi
  done
  if [ -n "$busy" ]; then
    red "Ces ports sont déjà utilisés par un autre programme :$busy"
    red "Arrêter ce programme, ou changer WEB_HOST_PORT / API_HOST_PORT dans le fichier .env (créé au premier lancement), puis relancer."
    exit 1
  fi
fi

say "Démarrage (première fois : 10 à 15 minutes, les lancements suivants sont rapides)"
make demo

say "Prêt"
web_port="$(sed -n 's/^WEB_HOST_PORT=//p' .env 2> /dev/null | head -1)"
url="http://localhost:${web_port:-3000}"
echo "Site            : $url"
echo "Boîte mail test : http://localhost:$(sed -n 's/^MAILPIT_HOST_PORT=//p' .env 2> /dev/null | head -1 | grep . || echo 54324)"
echo "Comptes         : voir ci-dessous (aussi dans le fichier .demo-accounts.txt)"
echo
cat .demo-accounts.txt 2> /dev/null || true
echo
echo "Arrêter : ./start.sh stop     Tout refaire à zéro : ./start.sh reset"

# Ouvre le navigateur (désactivable : NO_BROWSER=1 ./start.sh).
if [ -z "${NO_BROWSER:-}" ]; then
  if command -v open > /dev/null 2>&1; then open "$url" || true
  elif command -v xdg-open > /dev/null 2>&1; then xdg-open "$url" > /dev/null 2>&1 || true
  fi
fi
