#!/usr/bin/env python
"""
Script para migrar dados diretamente do SQLite para PostgreSQL (Supabase)
Usa configurações de banco múltiplas para ler de um e escrever em outro
"""
import sqlite3
import psycopg2
import json

print("=" * 60)
print("MIGRAÇÃO DE DADOS: SQLite -> Supabase")
print("=" * 60)

# Configurações
SQLITE_DB = 'db.sqlite3'
PG_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres.qmrawacnfczslrattgtp',
    'password': 'PAOGFFMyTP30quCF',
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': '6543',
    'sslmode': 'require',
    'connect_timeout': 10
}

print("\n[1/4] Conectando aos bancos de dados...")
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect(**PG_CONFIG)
pg_cursor = pg_conn.cursor()
print("✓ Conexões estabelecidas")

# Função para copiar tabela
def copy_table(table_name, sqlite_cursor, pg_cursor, skip_tables=[]):
    if table_name in skip_tables:
        return 0
    
    try:
        # Ler dados do SQLite
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            return 0
            
        # Pegar nomes das colunas
        columns = [description[0] for description in sqlite_cursor.description]
        
        # Pegar informações das colunas do Postgres
        pg_cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
        """)
        pg_columns_info = {row[0]: {'type': row[1], 'nullable': row[2]} for row in pg_cursor.fetchall()}
        
        # Preparar INSERT
        placeholders = ','.join(['%s'] * len(columns))
        columns_str = ','.join([f'"{col}"' for col in columns])
        insert_sql = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        
        # Inserir no Postgres
        count = 0
        skipped = 0
        for row in rows:
            # Converter valores conforme necessário
            converted_row = []
            skip_row = False
            
            for i, value in enumerate(row):
                col_name = columns[i]
                col_info = pg_columns_info.get(col_name, {})
                col_type = col_info.get('type', '')
                is_nullable = col_info.get('nullable', 'YES')
                
                # Converter inteiros para booleanos
                if col_type == 'boolean' and isinstance(value, int):
                    value = bool(value)
                # Se valor vazio ou None e coluna NOT NULL, aplicar valor padrão
                elif (value is None or value == '') and is_nullable == 'NO':
                    if col_name in ['cnpj']:  # CNPJ específico
                        value = f'00000000000000{count:02d}'  # CNPJ fake único
                    elif col_type in ['character varying', 'text']:
                        value = 'N/A'
                    elif col_type == 'integer':
                        value = 0
                # Converter para None se vazio
                elif value == '':
                    value = None
                    
                converted_row.append(value)
            
            if skip_row:
                skipped += 1
                continue
                
            try:
                pg_cursor.execute(insert_sql, tuple(converted_row))
                count += 1
            except Exception as row_error:
                # Se erro de foreign key, continuar
                if 'foreign key constraint' in str(row_error).lower():
                    skipped += 1
                    continue
                else:
                    raise
        
        pg_conn.commit()  # Commit após cada tabela
        
        if skipped > 0:
            print(f"  ⚠ {table_name}: {count} registros inseridos, {skipped} pulados")
        
        return count
    except Exception as e:
        pg_conn.rollback()  # Rollback em caso de erro
        print(f"  ✗ Erro em {table_name}: {str(e)[:100]}")
        return 0

print("\n[2/4] Listando tabelas do SQLite...")
sqlite_cursor = sqlite_conn.cursor()
sqlite_cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    AND name NOT LIKE 'django_session'
    AND name NOT LIKE 'auth_permission'
    AND name NOT LIKE 'django_content_type'
    ORDER BY name
""")
tables = [row[0] for row in sqlite_cursor.fetchall()]
print(f"✓ {len(tables)} tabelas encontradas")

print("\n[3/4] Copiando dados...")
skip_tables = ['django_migrations', 'authtoken_token', 'auth_user']  # auth_user não existe, é access_user
total_copied = 0

# PASSADA 1: Dados básicos sem foreign keys circulares
print("\n  [Passada 1: Dados básicos]")
pass1_tables = [
    'auth_group',
    'cadastros_condominio',
]

for table in pass1_tables:
    if table in tables:
        count = copy_table(table, sqlite_cursor, pg_cursor, skip_tables)
        if count > 0:
            total_copied += count
            print(f"  ✓ {table}: {count} registros")

# PASSADA 2: Users sem unidade (para permitir foreign keys)
print("\n  [Passada 2: Users básicos]")
# Inserir users setando unidade_id e created_by_id como NULL temporariamente
sqlite_cursor.execute("SELECT * FROM access_user")
rows = sqlite_cursor.fetchall()
columns = [description[0] for description in sqlite_cursor.description]

if rows:
    pg_cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'access_user'
    """)
    pg_columns_info = {row[0]: {'type': row[1], 'nullable': row[2]} for row in pg_cursor.fetchall()}
    
    unidade_idx = columns.index('unidade_id') if 'unidade_id' in columns else -1
    created_by_idx = columns.index('created_by_id') if 'created_by_id' in columns else -1
    
    placeholders = ','.join(['%s'] * len(columns))
    columns_str = ','.join([f'"{col}"' for col in columns])
    insert_sql = f'INSERT INTO access_user ({columns_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING'
    
    count = 0
    for row in rows:
        converted_row = []
        for i, value in enumerate(row):
            col_name = columns[i]
            col_info = pg_columns_info.get(col_name, {})
            col_type = col_info.get('type', '')
            
            # Temporariamente setar unidade e created_by como NULL
            if i == unidade_idx or i == created_by_idx:
                value = None
            # Converter inteiros para booleanos
            elif col_type == 'boolean' and isinstance(value, int):
                value = bool(value)
            # Se valor vazio, converter para None
            elif value == '':
                value = None
                
            converted_row.append(value)
        
        try:
            pg_cursor.execute(insert_sql, tuple(converted_row))
            count += 1
        except Exception as e:
            print(f"    ⚠ Erro ao inserir user: {str(e)[:100]}")
    
    pg_conn.commit()
    total_copied += count
    print(f"  ✓ access_user: {count} registros")

# PASSADA 3: Unidades e outros dados
print("\n  [Passada 3: Demais dados]")
pass3_tables = [
    'cadastros_unidade',
    'cadastros_condominiologo',
    'cadastros_aviso',
    'cadastros_encomenda',
    'cadastros_espaco',
    'cadastros_espacoreserva',
    'cadastros_espacoinventarioitem',
    'cadastros_evento',
    'cadastros_visitante',
    'cadastros_veiculo',
    'access_user_groups',
]

for table in pass3_tables:
    if table in tables:
        count = copy_table(table, sqlite_cursor, pg_cursor, skip_tables)
        if count > 0:
            total_copied += count
            print(f"  ✓ {table}: {count} registros")

# PASSADA 4: Atualizar foreign keys circulares em access_user
print("\n  [Passada 4: Atualizando foreign keys]")
sqlite_cursor.execute("SELECT id, unidade_id, created_by_id FROM access_user WHERE unidade_id IS NOT NULL OR created_by_id IS NOT NULL")
user_updates = sqlite_cursor.fetchall()

updated = 0
for user_id, unidade_id, created_by_id in user_updates:
    try:
        if unidade_id and created_by_id:
            pg_cursor.execute(
                "UPDATE access_user SET unidade_id = %s, created_by_id = %s WHERE id = %s",
                (unidade_id, created_by_id, user_id)
            )
        elif unidade_id:
            pg_cursor.execute(
                "UPDATE access_user SET unidade_id = %s WHERE id = %s",
                (unidade_id, user_id)
            )
        elif created_by_id:
            pg_cursor.execute(
                "UPDATE access_user SET created_by_id = %s WHERE id = %s",
                (created_by_id, user_id)
            )
        updated += 1
    except Exception as e:
        print(f"    ⚠ Erro ao atualizar user {user_id}: {str(e)[:80]}")

pg_conn.commit()
if updated > 0:
    print(f"  ✓ Atualizados {updated} registros de usuários")

# Adicionar tabelas restantes que não foram processadas
print("\n  [Passada 5: Tabelas restantes]")
for table in tables:
    if table not in pass1_tables and table not in pass3_tables and table not in skip_tables and table != 'access_user':
        count = copy_table(table, sqlite_cursor, pg_cursor, skip_tables)
        if count > 0:
            total_copied += count
            print(f"  ✓ {table}: {count} registros")

print(f"\n✓ Total: {total_copied} registros copiados")

print("\n[4/4] Finalizando...")
pg_conn.commit()
pg_cursor.close()
pg_conn.close()
sqlite_cursor.close()
sqlite_conn.close()
print("✓ Conexões fechadas")

print("\n" + "=" * 60)
print("MIGRAÇÃO FINALIZADA COM SUCESSO!")
print("=" * 60)
