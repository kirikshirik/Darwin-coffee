#!/bin/bash
# Удобный скрипт запуска Docker контейнера Darwin Coffee на localhostе
# Использование: ./docker-run.sh [up|down|logs|shell|build]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для печати с цветом
print_status() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Проверка Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker не найден. Установи Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    print_success "Docker установлен"
}

# Команда: запуск контейнера
cmd_up() {
    print_status "Запуск Darwin Coffee в Docker..."
    if [ "$1" == "build" ]; then
        print_status "Пересборка контейнера..."
        docker-compose up --build
    else
        docker-compose up
    fi
}

# Команда: остановка
cmd_down() {
    print_status "Остановка контейнера..."
    docker-compose down
    print_success "Контейнер остановлен"
}

# Команда: логи
cmd_logs() {
    docker-compose logs -f "${@:2}"
}

# Команда: shell в контейнере
cmd_shell() {
    print_status "Вход в контейнер (bash)..."
    docker-compose exec darwin-coffee bash
}

# Команда: статус
cmd_status() {
    print_status "Статус контейнеров:"
    docker-compose ps
}

# Команда: очистка (удалить всё)
cmd_clean() {
    print_warning "Удаление контейнеров, образов и БД..."
    read -p "Вы уверены? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v --rmi all
        print_success "Всё удалено"
    else
        print_status "Отменено"
    fi
}

# Команда: помощь
cmd_help() {
    cat << EOF
${BLUE}Darwin Coffee — Docker запуск${NC}

ИСПОЛЬЗОВАНИЕ:
    $0 [КОМАНДА] [ОПЦИИ]

КОМАНДЫ:
    up [build]      Запустить контейнер (build — пересборка)
    down            Остановить контейнер (БД сохраняется)
    logs [сервис]   Показать логи (tail -f)
    shell           Войти в контейнер (bash)
    status          Статус контейнеров
    clean           Удалить всё (контейнеры, образы, БД)
    help            Эта справка

ПРИМЕРЫ:
    $0 up                   # Запуск (если уже собран)
    $0 up build             # Первый запуск (сборка)
    $0 logs                 # Логи приложения
    $0 shell                # Вход в контейнер
    $0 down                 # Остановка

ССЫЛКИ:
    После запуска: http://localhost:8000/app
    Документация: ./DOCKER.md
    Архитектура:  ./CLAUDE.md

EOF
}

# Main
main() {
    local cmd="${1:-help}"

    check_docker

    case "$cmd" in
        up)
            cmd_up "$2"
            ;;
        down)
            cmd_down
            ;;
        logs)
            cmd_logs "$@"
            ;;
        shell)
            cmd_shell
            ;;
        status)
            cmd_status
            ;;
        clean)
            cmd_clean
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_warning "Неизвестная команда: $cmd"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
