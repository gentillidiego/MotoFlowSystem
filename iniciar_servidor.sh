#!/bin/bash
# Script para gerenciar o servidor Moto Flow via systemd --user

echo "Reiniciando o serviço MotoFlow via systemd..."
systemctl --user daemon-reload
systemctl --user restart motoflow

echo "Status do serviço:"
systemctl --user status motoflow
