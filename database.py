import sqlite3
import logging
from pathlib import Path

DB = Path(__file__).with_name("estoque.db")

def query(sql, params=(), one=False):
    try:
        with sqlite3.connect(DB) as c:
            c.row_factory = sqlite3.Row
            cur = c.execute(sql, params)
            rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    except sqlite3.Error as e:
        logging.error("Erro na query SQL: %s | SQL: %s", e, sql)
        raise

def execute(sql, params=()):
    try:
        with sqlite3.connect(DB) as c:
            c.execute(sql, params)
    except sqlite3.Error as e:
        logging.error("Erro ao executar SQL: %s | SQL: %s", e, sql)
        raise

def insert(sql, params=()):
    try:
        with sqlite3.connect(DB) as c:
            cur = c.execute(sql, params)
            return cur.lastrowid
    except sqlite3.Error as e:
        logging.error("Erro ao inserir SQL: %s | SQL: %s", e, sql)
        raise

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS motos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modelo TEXT, chassi TEXT, placa TEXT, cor TEXT, ano TEXT,
                origem TEXT, preco_aquisicao REAL, preco_venda REAL,
                vendido INTEGER DEFAULT 0,
                manter_catalogo INTEGER DEFAULT 0,
                km INTEGER,
                fotos_url TEXT,
                descricao TEXT
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS moto_custos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moto_id INTEGER NOT NULL,
                descricao TEXT, valor REAL,
                FOREIGN KEY(moto_id) REFERENCES motos(id) ON DELETE CASCADE
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS leads(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT, telefone TEXT, cpf TEXT, data_nasc TEXT,
                produto_id INTEGER, temperatura TEXT, observacoes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS vendas(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT, telefone TEXT, cpf TEXT, data_nasc TEXT,
                endereco TEXT, bairro TEXT, cidade TEXT, cep TEXT, email TEXT,
                produto_id INTEGER, data_venda TEXT, lead_id INTEGER,
                condicao_pagamento TEXT
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS venda_custos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL,
                descricao TEXT, valor REAL,
                FOREIGN KEY(venda_id) REFERENCES vendas(id) ON DELETE CASCADE
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS financeiro_custos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ano INTEGER, mes INTEGER,
                descricao TEXT, valor REAL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS financeiro_despesas(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ano INTEGER, mes INTEGER,
                descricao TEXT, valor REAL
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS transferencias(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL,
                responsavel TEXT, -- 'Loja' ou 'Cliente'
                status TEXT,      -- Etapa atual
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                observacoes TEXT,
                FOREIGN KEY(venda_id) REFERENCES vendas(id) ON DELETE CASCADE
            )""")
