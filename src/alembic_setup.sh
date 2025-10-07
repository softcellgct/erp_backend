#!/bin/bash

function select_option {
    options=("$@")
    PS3="Please select an option: "
    select opt in "${options[@]}"; do
        if [[ -n "$opt" ]]; then
            echo "$opt"
            break
        else
            echo "Invalid option. Try again."
        fi
    done
}


commands=("revision" "upgrade")
command=$(select_option "${commands[@]}")

case $command in
revision)
    read -p "Enter the message for the revision: " message
    alembic revision --autogenerate -m "$message"
    ;;
upgrade)
    read -p "Enter the revision to upgrade to (default: head): " revision
    revision=${revision:-head}
    alembic upgrade "$revision"
    ;;
*)
    show_help
    exit 1
    ;;
esac