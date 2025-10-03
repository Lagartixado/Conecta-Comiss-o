import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import date, datetime
from functools import wraps
from decimal import Decimal

app = Flask(__name__)

#LEMBRAR DE OCULTAR PARA VERSAO FINAL
app.secret_key = 'b3fd6e49d7724c57bdc905f2ee4ac3e5b9151d1c7aa134d4b98c73c1326f03de' 
#LEMBRAR DE OCULTAR PARA VERSAO FINAL

#warp para deixar o codigo mais bonito e deixar matheus feliz

# Decorador para exigir login
def login_necessario(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'login' not in session:
            flash('Você precisa fazer login primeiro.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para exigir login de administrador
def admin_necessario(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'login' not in session or session.get('tipo_usuario') != 'admin':
            flash('Acesso restrito a administradores.')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def conexao_mysql():
    conn = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="aluno",
        database="conectac"
    )
    cursor = conn.cursor()

    conn.commit()
    cursor.close()
    return conn

# Rota para exibir links úteis
@app.route('/links', methods=['GET'])
@login_necessario
def links():
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, url FROM links ORDER BY id DESC")
    links = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('links.html', links=links)

# Rota para adicionar link (apenas admin)
@app.route('/adicionar_link', methods=['POST'])
@admin_necessario
def adicionar_link():
    nome = request.form['nome']
    url_link = request.form['url']
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO links (nome, url) VALUES (%s, %s)", (nome, url_link))
        conn.commit()
        flash('Link adicionado com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao adicionar link.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('links'))

# Rota para deletar link (apenas admin)
@app.route('/deletar_link/<int:link_id>', methods=['POST'])
@admin_necessario
def deletar_link(link_id):
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM links WHERE id = %s", (link_id,))
        conn.commit()
        flash('Link excluído com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao excluir link.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('links'))

# Rota para visualizar fundo da comissão e despesas
@app.route('/fundo_comissao', methods=['GET'])
@login_necessario

def fundo_comissao():
    pagina = int(request.args.get('pagina', 1))
    por_pagina = 10
    filtro_tipo = request.args.get('tipo')  # 'arrecadacao', 'despesa', ou None
    filtro_tipo_arrecadacao = request.args.get('tipo_arrecadacao')  # 'Eventos', 'Rifas', 'Produtos', ou None
    filtro_tipo_despesa = request.args.get('tipo_despesa')  # 'Eventos', 'Rifas', 'Produtos', ou None
    filtro_categoria = request.args.get('categoria')  # 'Eventos', 'Rifas', 'Produtos', ou None
    filtro_produto = request.args.get('produto')  # Produto selecionado
    data_inicio = request.args.get('data_inicio')  # Data inicial para filtro
    data_fim = request.args.get('data_fim')  # Data final para filtro
    ordenacao = request.args.get('ordenacao')  # 'maior_valor', 'menor_valor', ou None

    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT tipo FROM filtros ORDER BY tipo")
    tipos = cursor.fetchall()

    # Buscar sub-tipos para arrecadações
    cursor.execute("SELECT DISTINCT tipo FROM arrecadacoes ORDER BY tipo")
    sub_tipos_arrecadacao = cursor.fetchall()

    # Buscar sub-tipos para despesas
    cursor.execute("SELECT DISTINCT tipo FROM despesas ORDER BY tipo")
    sub_tipos_despesa = cursor.fetchall()

    # Buscar produtos de ambas as tabelas
    cursor.execute("SELECT DISTINCT produto FROM despesas WHERE produto IS NOT NULL ORDER BY produto")
    produtos_despesas = cursor.fetchall()
    cursor.execute("SELECT DISTINCT produto FROM arrecadacoes WHERE produto IS NOT NULL ORDER BY produto")
    produtos_arrecadacoes = cursor.fetchall()
    # Combinar os resultados removendo duplicatas
    produtos_set = set()
    for p in produtos_despesas:
        if p['produto']:
            produtos_set.add(p['produto'])
    for p in produtos_arrecadacoes:
        if p['produto']:
            produtos_set.add(p['produto'])
    produtos = [{'produto': p} for p in sorted(produtos_set)]

    # Buscar itens por tipo
    cursor.execute("SELECT DISTINCT tipo, item FROM despesas WHERE item IS NOT NULL AND item != '' ORDER BY tipo, item")
    itens_rows = cursor.fetchall()
    itens_por_tipo = {}
    for row in itens_rows:
        tipo = row['tipo']
        item = row['item']
        if tipo not in itens_por_tipo:
            itens_por_tipo[tipo] = []
        itens_por_tipo[tipo].append(item)

    # Fundo: soma de todas arrecadações
    cursor.execute("SELECT SUM(valor) as fundo FROM arrecadacoes")
    fundo_row = cursor.fetchone()
    fundo_disponivel = round(float(fundo_row['fundo']), 2) if fundo_row and fundo_row['fundo'] is not None else 0.0

    # Buscar despesas e arrecadações com nome do admin
    cursor.execute("SELECT d.id, d.nome, d.descricao, d.valor, d.data_criacao, d.tipo, d.item, d.produto, 'despesa' as tipo_registro, a.nome as admin_nome FROM despesas d LEFT JOIN admins a ON d.admin_id = a.id")
    despesas = cursor.fetchall()
    cursor.execute("SELECT a.id_arrecadacao as id, a.valor, a.descricao, a.data_arrecadacao, a.matricula, a.tipo, a.produto, 'arrecadacao' as tipo_registro, ad.nome as admin_nome FROM arrecadacoes a LEFT JOIN admins ad ON a.admin_id = ad.id")
    arrecadacoes = cursor.fetchall()

    # Calcular total de arrecadações (só dos alunos)
    total_arrecadacoes = round(sum([float(a['valor']) for a in arrecadacoes]), 2) if arrecadacoes else 0.0

    # Subtrai despesas do fundo
    total_despesas = round(sum([float(d['valor']) for d in despesas]), 2) if despesas else 0.0
    fundo_disponivel -= total_despesas

    # Unir despesas e arrecadações em uma lista única
    registros = []
    for d in despesas:
        data = d['data_criacao']
        if data and not isinstance(data, datetime):
            try:
                data = datetime.combine(data, datetime.min.time())
            except Exception:
                pass
        registros.append({
            'tipo': 'despesa',
            'sub_tipo': d['tipo'],
            'id': d['id'],
            'nome': d['nome'],
            'descricao': d['descricao'],
            'valor': d['valor'],
            'data': data,
            'item': d['item'],
            'produto': d['produto'],
            'admin_nome': d['admin_nome']
        })
    for a in arrecadacoes:
        # Buscar nome do aluno
        cursor2 = conn.cursor(dictionary=True)
        cursor2.execute("SELECT nome FROM alunos WHERE matricula = %s", (a['matricula'],))
        aluno_row = cursor2.fetchone()
        nome_aluno = aluno_row['nome'] if aluno_row else a['matricula']
        cursor2.close()
        data = a['data_arrecadacao']
        if data and not isinstance(data, datetime):
            try:
                data = datetime.combine(data, datetime.min.time())
            except Exception:
                pass
        registros.append({
            'tipo': 'arrecadacao',
            'sub_tipo': a['tipo'],
            'id': a['id'],
            'nome': nome_aluno,
            'descricao': a['descricao'],
            'valor': a['valor'],
            'data': data,
            'produto': a['produto'],
            'admin_nome': a['admin_nome']
        })

    # Filtro por tipo
    if filtro_tipo == 'arrecadacao':
        registros = [r for r in registros if r['tipo'] == 'arrecadacao']
    elif filtro_tipo == 'despesa':
        registros = [r for r in registros if r['tipo'] == 'despesa']

    # Filtro por sub-tipo arrecadação
    if filtro_tipo_arrecadacao:
        registros = [r for r in registros if r.get('tipo') == 'arrecadacao' and r.get('sub_tipo') == filtro_tipo_arrecadacao]

    # Filtro por sub-tipo despesa
    if filtro_tipo_despesa:
        registros = [r for r in registros if r.get('tipo') == 'despesa' and r.get('sub_tipo') == filtro_tipo_despesa]

    # Filtro por categoria
    if filtro_categoria:
        registros = [r for r in registros if r.get('sub_tipo') == filtro_categoria]

    # Filtro por produto
    if filtro_produto:
        registros = [r for r in registros if r.get('produto') == filtro_produto]

    # Validação das datas
    if data_inicio and data_fim:
        try:
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
            data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
            if data_fim_dt < data_inicio_dt:
                flash('A data final não pode ser menor que a data inicial.', 'error')
                # Redirecionar sem os parâmetros de data inválidos
                return redirect(url_for('fundo_comissao', pagina=pagina, tipo=filtro_tipo, categoria=filtro_categoria, ordenacao=ordenacao))
        except ValueError:
            flash('Formato de data inválido.', 'error')
            return redirect(url_for('fundo_comissao', pagina=pagina, tipo=filtro_tipo, categoria=filtro_categoria, ordenacao=ordenacao))

    # Filtro por data
    if data_inicio:
        try:
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
            registros = [r for r in registros if r['data'] and r['data'] >= data_inicio_dt]
        except ValueError:
            pass  # Ignorar filtro se data inválida

    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
            # Adicionar um dia para incluir a data final
            data_fim_dt = data_fim_dt.replace(hour=23, minute=59, second=59)
            registros = [r for r in registros if r['data'] and r['data'] <= data_fim_dt]
        except ValueError:
            pass  # Ignorar filtro se data inválida

    # Ordenação por valor
    if ordenacao == 'maior_valor':
        registros = sorted(registros, key=lambda x: float(x['valor']), reverse=True)
    elif ordenacao == 'menor_valor':
        registros = sorted(registros, key=lambda x: float(x['valor']))
    else:
        # Ordenar por data (mais recente primeiro)
        registros = sorted(registros, key=lambda x: x['data'] if x['data'] else datetime.min, reverse=True)

    # Paginação
    total_paginas = (len(registros) + por_pagina - 1) // por_pagina
    inicio = (pagina - 1) * por_pagina
    fim = inicio + por_pagina
    registros_paginados = registros[inicio:fim]

    # Calcular total do filtro (soma dos valores dos registros filtrados, despesas negativas)
    total_filtro = round(sum([float(r['valor']) if r['tipo'] == 'arrecadacao' else -float(r['valor']) for r in registros]), 2) if registros else 0.0

    cursor.close()
    conn.close()
    return render_template('fundo_comissao.html', fundo_disponivel=fundo_disponivel, registros_paginados=registros_paginados, total_paginas=total_paginas, pagina_atual=pagina, total_despesas=total_despesas, total_arrecadacoes=total_arrecadacoes, total_filtro=total_filtro, filtro_tipo=filtro_tipo, ordenacao=ordenacao, data_inicio=data_inicio, data_fim=data_fim, filtro_tipo_arrecadacao=filtro_tipo_arrecadacao, filtro_tipo_despesa=filtro_tipo_despesa, filtro_produto=filtro_produto, filtro_categoria=filtro_categoria, sub_tipos_arrecadacao=sub_tipos_arrecadacao, sub_tipos_despesa=sub_tipos_despesa, produtos=produtos, itens_por_tipo=itens_por_tipo, tipos=tipos)

# Rota para deletar despesa (apenas admin)
@app.route('/deletar_despesa', methods=['POST'])
@admin_necessario
def deletar_despesa():
    id_despesa = request.form.get('id_despesa')
    if not id_despesa:
        flash('ID da despesa não fornecido.')
        return redirect(url_for('fundo_comissao'))
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM despesas WHERE id = %s", (id_despesa,))
        conn.commit()
        flash('Despesa excluída com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao excluir despesa.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('fundo_comissao'))

# Rota para deletar arrecadacao (apenas admin)
@app.route('/deletar_arrecadacao', methods=['POST'])
@admin_necessario
def deletar_arrecadacao():
    id_arrecadacao = request.form.get('id_arrecadacao')
    if not id_arrecadacao:
        flash('ID da arrecadação não fornecido.')
        return redirect(url_for('fundo_comissao'))
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM arrecadacoes WHERE id_arrecadacao = %s", (id_arrecadacao,))
        conn.commit()
        flash('Arrecadação excluída com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao excluir arrecadação.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('fundo_comissao'))

# Rota para adicionar despesa (apenas admin)
@app.route('/adicionar_despesa', methods=['POST'])
@admin_necessario
def adicionar_despesa():
    nome = request.form['nome']
    descricao = request.form['descricao']
    valor = Decimal(request.form['valor']).quantize(Decimal('0.01'))
    tipo = request.form['tipo']
    item = request.form.get('item', '')
    produto = request.form['produto']
    if valor <= 0:
        flash('O valor da despesa deve ser maior que zero.')
        return redirect(url_for('fundo_comissao'))
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO despesas (nome, descricao, valor, tipo, item, produto, admin_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (nome, descricao, float(valor), tipo, item, produto, session['id']))
        conn.commit()
        flash('Despesa adicionada com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao adicionar despesa.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('fundo_comissao'))

@app.route('/registrar_arrecadacao', methods=['GET', 'POST'])
@login_necessario
def registrar_arrecadacao():

    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT matricula, nome FROM alunos ORDER BY nome")
    alunos = cursor.fetchall()
    cursor.execute("SELECT nome, tipo FROM filtros ORDER BY tipo, nome")
    filtros = cursor.fetchall()

    if request.method == 'POST':
        matricula = request.form['matricula']
        valor = Decimal(request.form['valor']).quantize(Decimal('0.01'))
        data_arrecadacao = request.form['data_arrecadacao']
        descricao = request.form['descricao']
        produto = request.form['produto']
        tipo = request.form['tipo']

        cursor3 = conn.cursor()
        try:
            if session.get('tipo_usuario') == 'admin':
                query = "INSERT INTO arrecadacoes (matricula, valor, data_arrecadacao, descricao, produto, tipo, admin_id) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                cursor3.execute(query, (matricula, float(valor), data_arrecadacao, descricao, produto, tipo, session['id']))
            else:
                query = "INSERT INTO arrecadacoes (matricula, valor, data_arrecadacao, descricao, produto, tipo) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor3.execute(query, (matricula, float(valor), data_arrecadacao, descricao, produto, tipo))
            conn.commit()
            flash('Arrecadação registrada com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Erro ao registrar arrecadação.', 'error')
        finally:
            cursor3.close()
        return redirect(url_for('registrar_arrecadacao'))

    cursor.close()
    conn.close()
    return render_template('registrar_arrecadacao.html', alunos=alunos, filtros=filtros, data_hoje=date.today().isoformat())

@app.route('/')
def index():
    if 'login' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'login' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        usuario = request.form['login']
        senha = request.form['senha']

        conn = conexao_mysql()
        cursor = conn.cursor(dictionary=True)
        cursor2 = conn.cursor(dictionary=True)

        query = "SELECT * FROM admins WHERE login = %s AND senha = %s"
        queryA = "SELECT login, matricula, nome FROM alunos WHERE login = %s AND senha = %s"
        cursor.execute(query, (usuario, senha))
        resultado = cursor.fetchone()
        cursor2.execute(queryA, (usuario, senha))
        resultadoA = cursor2.fetchone()

        cursor.close()
        conn.close()

        if resultado:
            session['login'] = resultado['login']
            session['tipo_usuario'] = 'admin'
            session['nivel'] = resultado['nivel']
            session['id'] = resultado['id']
            return redirect(url_for('home'))

        elif resultadoA:
                session['login'] = resultadoA['login']
                session['tipo_usuario'] = 'aluno'
                session['matricula'] = resultadoA['matricula'] or resultadoA['id']  # Fallback to id if matricula is null
                return redirect(url_for('home'))

        else:
            flash('Usuário ou senha inválidos!', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/home')
@login_necessario
def home():
    return render_template('home.html', usuario=session['login'])

@app.route('/Galuno', methods=['GET', 'POST'])
@admin_necessario
def Galuno():
    if request.method == 'POST':
        rnome = request.form['nome_A']
        rsenha = request.form['senha_A']
        confirmar_senha = request.form['confirmar_senha_A']
        rlogin = request.form['login_A']
        rmatricula = request.form['matricula_A']
        rturma = request.form['turma_A']

        if rsenha != confirmar_senha:
            flash('As senhas não coincidem!', 'error')
            return redirect(url_for('Galuno'))

        if len(rsenha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres!', 'error')
            return redirect(url_for('Galuno'))

        if len(rsenha) > 12:
            flash('A senha deve ter no máximo 12 caracteres!', 'error')
            return redirect(url_for('Galuno'))

        if len(rmatricula) > 9:
            flash('A matrícula deve ter no máximo 9 caracteres!', 'error')
            return redirect(url_for('Galuno'))

        conn = conexao_mysql()
        cursor = conn.cursor(dictionary=True)

        # Check if matricula already exists
        cursor.execute("SELECT * FROM alunos WHERE matricula = %s", (rmatricula,))
        if cursor.fetchone():
            flash('Matrícula já cadastrada!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('Galuno'))

        # Check if login already exists
        cursor.execute("SELECT * FROM alunos WHERE login = %s", (rlogin,))
        if cursor.fetchone():
            flash('Login já cadastrado!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('Galuno'))

        query = "INSERT INTO alunos (nome, senha, login, matricula, id_turma) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (rnome, rsenha, rlogin, rmatricula, rturma))
        conn.commit()

        cursor.close()
        conn.close()

        flash('Aluno cadastrado com sucesso!', 'success')

    # Buscar todas as turmas cadastradas para o dropdown
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_turma, nome FROM turmas ORDER BY nome")
    turmas = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('Galuno.html', turmas=turmas)
    
@app.route('/logout')
def logout():
    session.pop('login', None)
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('login'))

@app.route('/EsqS')
def EsqS():
    return render_template('EsqS.html')
    

@app.route('/editar_alunos')
@admin_necessario
def editar_alunos():
    pagina = int(request.args.get('pagina', 1))
    por_pagina = 10
    filtro_turma = request.args.get('turma')
    filtro_meta = request.args.get('meta')  # 'acima', 'abaixo', 'igual', ou None
    ordenacao = request.args.get('ordenacao', 'alfabetica')  # 'alfabetica', 'menor_arrecadado', 'maior_arrecadado'

    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Calcular meta individual como total de despesas dividido pela quantidade de alunos
    cursor.execute("SELECT COUNT(*) as total_alunos FROM alunos")
    total_alunos_row = cursor.fetchone()
    total_alunos = total_alunos_row['total_alunos'] if total_alunos_row and total_alunos_row['total_alunos'] is not None else 1
    cursor.execute("SELECT SUM(valor) as total_despesas FROM despesas")
    total_despesas_row = cursor.fetchone()
    total_despesas = float(total_despesas_row['total_despesas']) if total_despesas_row and total_despesas_row['total_despesas'] is not None else 0.0
    meta_individual = round(total_despesas / total_alunos, 2) if total_alunos > 0 else 0.0

    # Buscar todos os alunos com informações da turma e arrecadação
    query = """
    SELECT a.matricula, a.nome, a.login, t.nome as nome_turma, t.id_turma,
           (SELECT SUM(valor) FROM arrecadacoes ar WHERE ar.matricula = a.matricula) as total_arrecadado
    FROM alunos a
    LEFT JOIN turmas t ON a.id_turma = t.id_turma
    """
    cursor.execute(query)
    todos_alunos = cursor.fetchall()

    # Filtro por turma
    if filtro_turma:
        todos_alunos = [al for al in todos_alunos if str(al['id_turma']) == str(filtro_turma)]

    # Filtro por meta
    if filtro_meta == 'acima':
        todos_alunos = [al for al in todos_alunos if (al['total_arrecadado'] or 0) > meta_individual]
    elif filtro_meta == 'abaixo':
        todos_alunos = [al for al in todos_alunos if (al['total_arrecadado'] or 0) < meta_individual]
    elif filtro_meta == 'igual':
        todos_alunos = [al for al in todos_alunos if round((al['total_arrecadado'] or 0),2) == round(meta_individual,2)]

    # Ordenação
    if ordenacao == 'menor_arrecadado':
        todos_alunos = sorted(todos_alunos, key=lambda x: (x['total_arrecadado'] or 0))
    elif ordenacao == 'maior_arrecadado':
        todos_alunos = sorted(todos_alunos, key=lambda x: (x['total_arrecadado'] or 0), reverse=True)
    else:  # alfabetica
        todos_alunos = sorted(todos_alunos, key=lambda x: x['nome'].lower())

    # Paginação
    total_paginas = (len(todos_alunos) + por_pagina - 1) // por_pagina
    inicio = (pagina - 1) * por_pagina
    fim = inicio + por_pagina
    alunos = todos_alunos[inicio:fim]

    # Buscar todas as turmas
    cursor.execute("SELECT id_turma, nome FROM turmas ORDER BY nome")
    turmas = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('editar_alunos.html', alunos=alunos, turmas=turmas, meta_individual=meta_individual, total_paginas=total_paginas, pagina_atual=pagina, filtro_turma=filtro_turma, filtro_meta=filtro_meta, ordenacao=ordenacao)


# Editar aluno sem alterar meta_aluno manualmente
@app.route('/editar_aluno', methods=['POST'])
@admin_necessario
def editar_aluno():
    matricula = request.form['matricula']
    nome = request.form['nome']
    login = request.form['login']
    senha = request.form['senha']
    id_turma = request.form['id_turma']
    nova_matricula = request.form.get('nova_matricula')

    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        # Handle matricula change
        if nova_matricula and nova_matricula != matricula:
            # Check if nova_matricula already exists
            cursor.execute("SELECT matricula FROM alunos WHERE matricula = %s", (nova_matricula,))
            if cursor.fetchone():
                flash('Matrícula já existe.', 'error')
                return redirect(url_for('editar_alunos'))
            # Update matricula
            cursor.execute("UPDATE alunos SET matricula = %s WHERE matricula = %s", (nova_matricula, matricula))
            matricula = nova_matricula  # Update for further updates

        # Update other fields
        if senha:
            query = """
            UPDATE alunos
            SET nome = %s, login = %s, senha = %s, id_turma = %s
            WHERE matricula = %s
            """
            cursor.execute(query, (nome, login, senha, id_turma, matricula))
        else:
            query = """
            UPDATE alunos
            SET nome = %s, login = %s, id_turma = %s
            WHERE matricula = %s
            """
            cursor.execute(query, (nome, login, id_turma, matricula))
        conn.commit()
        flash('Aluno atualizado com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao atualizar aluno.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('editar_alunos'))

@app.route('/deletar_aluno/<int:matricula>', methods=['POST'])
@admin_necessario
def deletar_aluno(matricula):
    
    conn = conexao_mysql()
    cursor = conn.cursor()
    
    try:
        # Verificar se aluno existe
        cursor.execute("SELECT * FROM alunos WHERE matricula = %s", (matricula,))
        if not cursor.fetchone():
            return {'error': 'Aluno não encontrado'}, 404
        
        # Deletar aluno
        cursor.execute("DELETE FROM alunos WHERE matricula = %s", (matricula,))
        conn.commit()
        
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}, 500
    finally:
        cursor.close()
        conn.close()

@app.route('/aluno/<int:matricula>')
@login_necessario
def dados_aluno(matricula):

    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Calcular meta individual como total de despesas dividido pela quantidade de alunos
    cursor.execute("SELECT COUNT(*) as total_alunos FROM alunos")
    total_alunos_row = cursor.fetchone()
    total_alunos = total_alunos_row['total_alunos'] if total_alunos_row and total_alunos_row['total_alunos'] is not None else 1
    cursor.execute("SELECT SUM(valor) as total_despesas FROM despesas")
    total_despesas_row = cursor.fetchone()
    total_despesas = float(total_despesas_row['total_despesas']) if total_despesas_row and total_despesas_row['total_despesas'] is not None else 0.0
    meta_individual = round(total_despesas / total_alunos, 2) if total_alunos > 0 else 0.0

    # Calcular ranking baseado apenas em rifas
    cursor.execute("""
        SELECT a.matricula, al.nome,
               SUM(a.valor) as total_rifas,
               ROW_NUMBER() OVER (ORDER BY SUM(a.valor) DESC) as posicao
        FROM arrecadacoes a
        JOIN alunos al ON a.matricula = al.matricula
        WHERE a.tipo = 'Rifas'
        GROUP BY a.matricula, al.nome
        ORDER BY total_rifas DESC
        LIMIT 3
    """)
    top_3_alunos = cursor.fetchall()

    # Buscar posição do aluno atual no ranking
    cursor.execute("""
        SELECT posicao FROM (
            SELECT a.matricula,
                   ROW_NUMBER() OVER (ORDER BY SUM(a.valor) DESC) as posicao
            FROM arrecadacoes a
            JOIN alunos al ON a.matricula = al.matricula
            WHERE a.tipo = 'Rifas'
            GROUP BY a.matricula
        ) ranking
        WHERE matricula = %s
    """, (matricula,))
    posicao_aluno = cursor.fetchone()

    query = """
    SELECT
        al.matricula,
        al.nome AS nome_aluno,
        t.nome AS nome_turma,
        (SELECT SUM(a.valor) FROM arrecadacoes a WHERE a.matricula = al.matricula) AS total_do_aluno,
        (SELECT SUM(a2.valor)
         FROM arrecadacoes a2
         JOIN alunos al2 ON a2.matricula = al2.matricula
         WHERE al2.id_turma = al.id_turma) AS total_da_turma,
        (SELECT SUM(valor) FROM arrecadacoes) AS total_geral,
        ar.valor,
        ar.descricao,
        ar.produto,
        ar.data_arrecadacao
    FROM alunos al
    JOIN turmas t ON al.id_turma = t.id_turma
    LEFT JOIN arrecadacoes ar ON ar.matricula = al.matricula
    WHERE al.matricula = %s
    """

    cursor.execute(query, (matricula,))
    dados = cursor.fetchall()
    conn.close()

    if not dados:
        flash('Aluno não encontrado.', 'error')
        return redirect(url_for('login'))

    aluno_info = dados[0]
    arrecadacoes = [d for d in dados if d['data_arrecadacao'] is not None]

    return render_template('aluno.html', aluno=aluno_info, arrecadacoes=arrecadacoes, meta_individual=meta_individual, top_3_alunos=top_3_alunos, posicao_aluno=posicao_aluno)

@app.route('/ranking')
@login_necessario
def ranking():
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Calcular ranking completo baseado apenas em rifas
    cursor.execute("""
        SELECT a.matricula, al.nome,
               SUM(a.valor) as total_rifas,
               ROW_NUMBER() OVER (ORDER BY SUM(a.valor) DESC) as posicao
        FROM arrecadacoes a
        JOIN alunos al ON a.matricula = al.matricula
        WHERE a.tipo = 'Rifas'
        GROUP BY a.matricula, al.nome
        ORDER BY total_rifas DESC
    """)
    ranking_completo = cursor.fetchall()

    # Buscar informações da turma para cada aluno
    for aluno in ranking_completo:
        cursor.execute("SELECT nome FROM turmas WHERE id_turma = (SELECT id_turma FROM alunos WHERE matricula = %s)", (aluno['matricula'],))
        turma_row = cursor.fetchone()
        aluno['turma'] = turma_row['nome'] if turma_row else 'N/A'

    conn.close()
    return render_template('ranking.html', ranking=ranking_completo)

@app.route('/minha_posicao/<int:matricula>')
@login_necessario
def minha_posicao(matricula):
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Buscar dados do aluno
    cursor.execute("SELECT nome FROM alunos WHERE matricula = %s", (matricula,))
    aluno_row = cursor.fetchone()

    if not aluno_row:
        flash('Aluno não encontrado.', 'error')
        conn.close()
        return redirect(url_for('home'))

    # Calcular posição do aluno no ranking
    cursor.execute("""
        SELECT posicao, total_rifas FROM (
            SELECT a.matricula,
                   SUM(a.valor) as total_rifas,
                   ROW_NUMBER() OVER (ORDER BY SUM(a.valor) DESC) as posicao
            FROM arrecadacoes a
            JOIN alunos al ON a.matricula = al.matricula
            WHERE a.tipo = 'Rifas'
            GROUP BY a.matricula
        ) ranking
        WHERE matricula = %s
    """, (matricula,))
    posicao_row = cursor.fetchone()

    # Buscar arrecadações de rifas do aluno
    cursor.execute("""
        SELECT valor, descricao, produto, data_arrecadacao
        FROM arrecadacoes
        WHERE matricula = %s AND tipo = 'Rifas'
        ORDER BY data_arrecadacao DESC
    """, (matricula,))
    arrecadacoes_rifas = cursor.fetchall()

    conn.close()

    posicao = posicao_row['posicao'] if posicao_row else None
    total_rifas = posicao_row['total_rifas'] if posicao_row else 0

    return render_template('minha_posicao.html', aluno=aluno_row, posicao=posicao, total_rifas=total_rifas, arrecadacoes=arrecadacoes_rifas)

@app.route('/cadastrar_admin', methods=['GET', 'POST'])
@admin_necessario
def cadastrar_admin():
    if request.method == 'POST':
        nome_admin = request.form['nome_admin']
        login_admin = request.form['login_admin']
        matricula_admin = request.form['matricula']
        senha_admin = request.form['senha_admin']
        confirmar_senha = request.form['confirmar_senha']
        telefone_admin = request.form.get('telefone_admin', '')

        if senha_admin != confirmar_senha:
            flash('As senhas não coincidem!', 'error')
            return redirect(url_for('cadastrar_admin'))

        if len(senha_admin) < 6:
            flash('A senha deve ter pelo menos 6 caracteres!', 'error')
            return redirect(url_for('cadastrar_admin'))

        conn = conexao_mysql()
        cursor = conn.cursor(dictionary=True)

        try:
            # Verificar se o login já existe
            cursor.execute("SELECT * FROM admins WHERE login = %s", (login_admin,))
            if cursor.fetchone():
                flash('Este login já está em uso!', 'error')
                return redirect(url_for('cadastrar_admin'))

            # Verificar se a matricula já existe
            cursor.execute("SELECT * FROM admins WHERE matricula = %s", (matricula_admin,))
            if cursor.fetchone():
                flash('Esta matricula já foi registrada!', 'error')
                return redirect(url_for('cadastrar_admin'))

            # Inserir novo administrador
            query = "INSERT INTO admins (nome, login, matricula, senha, telefone) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query, (nome_admin, login_admin, matricula_admin, senha_admin, telefone_admin))
            conn.commit()

            flash('Administrador cadastrado com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Erro ao cadastrar administrador.', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('cadastrar_admin'))

    # GET request
    return render_template('cadastrar_admin.html')

@app.route('/cadastrar_turma', methods=['GET', 'POST'])
@admin_necessario
def cadastrar_turma():
    if request.method == 'POST':
        nome = request.form['nome_turma']

        conn = conexao_mysql()
        cursor = conn.cursor()

        # Check if turma with same name already exists
        cursor.execute("SELECT * FROM turmas WHERE nome = %s", (nome,))
        if cursor.fetchone():
            flash('Turma com este nome já cadastrada!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('cadastrar_turma'))

        try:
            cursor.execute("INSERT INTO turmas (nome) VALUES (%s)", (nome,))
            conn.commit()
            flash('Turma cadastrada com sucesso!', 'success')
        except Exception as e:
            conn.rollback()
            flash('Erro ao cadastrar turma.', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('cadastrar_turma'))

    # Buscar todas as turmas cadastradas com paginação
    pagina = int(request.args.get('pagina', 1))
    por_pagina = 5

    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Contar total de turmas
    cursor.execute("SELECT COUNT(*) as total FROM turmas")
    total_turmas = cursor.fetchone()['total']
    total_paginas = (total_turmas + por_pagina - 1) // por_pagina

    # Buscar turmas da página atual ordenadas por ID
    offset = (pagina - 1) * por_pagina
    cursor.execute("SELECT id_turma, nome FROM turmas ORDER BY id_turma LIMIT %s OFFSET %s", (por_pagina, offset))
    turmas = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('cadastrar_turma.html', turmas=turmas, pagina_atual=pagina, total_paginas=total_paginas)

@app.route('/deletar_turma/<int:id_turma>', methods=['POST'])
@admin_necessario
def deletar_turma(id_turma):
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM turmas WHERE id_turma = %s", (id_turma,))
        conn.commit()
        flash('Turma excluída com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao excluir turma.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('cadastrar_turma'))

# Rota para listar, editar e deletar administradores
@app.route('/editar_admins')
@admin_necessario
def editar_admins():
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, login, matricula, telefone FROM admins WHERE nivel != 'admin0' ORDER BY nome")
    admins = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('editar_admins.html', admins=admins)


# Editar admin
@app.route('/editar_admin/<int:admin_id>', methods=['POST'])
@admin_necessario
def editar_admin(admin_id):
    nome = request.form.get('nome')
    login_admin = request.form['login']
    matricula = request.form.get('matricula')
    telefone = request.form.get('telefone')
    senha = request.form.get('senha', '')

    conn = conexao_mysql()
    cursor = conn.cursor()

    try:
        # First, check if admin exists
        cursor.execute("SELECT login, nivel FROM admins WHERE id = %s", (admin_id,))
        admin = cursor.fetchone()
        if not admin:
            flash('Administrador não encontrado.', 'error')
            return redirect(url_for('editar_admins'))

        admin_login = admin[0]
        nivel = admin[1]
        is_admin0 = nivel == 'admin0'

        # Check for duplicate login (excluding current admin)
        cursor.execute("SELECT id FROM admins WHERE login = %s AND id != %s", (login_admin, admin_id))
        duplicate = cursor.fetchone()
        if duplicate:
            flash('Este login já está em uso por outro administrador.', 'error')
            return redirect(url_for('editar_admins'))

        if is_admin0:
            # Para admin0, apenas atualizar login e senha
            if senha:
                query = "UPDATE admins SET login=%s, senha=%s WHERE id=%s"
                cursor.execute(query, (login_admin, senha, admin_id))
            else:
                query = "UPDATE admins SET login=%s WHERE id=%s"
                cursor.execute(query, (login_admin, admin_id))
        else:
            # Para outros admins, atualizar todos os campos
            # Allow nome, matricula, telefone to be None (NULL in DB) except login and senha (login required, senha can be blank to not change)
            if nome == '' or nome is None:
                nome = None
            if matricula == '' or matricula is None:
                matricula = None
            if telefone == '' or telefone is None:
                telefone = None

            # Check for duplicate matricula (excluding current admin)
            if matricula is not None:
                cursor.execute("SELECT id FROM admins WHERE matricula = %s AND id != %s", (matricula, admin_id))
                duplicate_mat = cursor.fetchone()
                if duplicate_mat:
                    flash('Esta matrícula já está registrada para outro administrador.', 'error')
                    return redirect(url_for('editar_admins'))

            if senha:
                query = "UPDATE admins SET nome=%s, login=%s, matricula=%s, telefone=%s, senha=%s WHERE id=%s"
                cursor.execute(query, (nome, login_admin, matricula, telefone, senha, admin_id))
            else:
                query = "UPDATE admins SET nome=%s, login=%s, matricula=%s, telefone=%s WHERE id=%s"
                cursor.execute(query, (nome, login_admin, matricula, telefone, admin_id))

        affected_rows = cursor.rowcount

        if affected_rows > 0:
            conn.commit()
            flash('Administrador atualizado com sucesso!', 'success')
        else:
            conn.rollback()
            flash('Nenhuma alteração foi feita.', 'info')

    except Exception as e:
        conn.rollback()
        print(f"DEBUG: Exception occurred: {str(e)}")
        flash(f'Erro ao atualizar administrador: {str(e)}')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('editar_admins'))

# Deletar admin
@app.route('/deletar_admin/<int:admin_id>', methods=['POST'])
@admin_necessario
def deletar_admin(admin_id):
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        # Não permitir deletar admin principal (nivel='admin0')
        cursor.execute("SELECT nivel FROM admins WHERE id = %s", (admin_id,))
        admin = cursor.fetchone()
        if admin and admin['nivel'] == 'admin0':
            flash('Não é permitido deletar o administrador principal.', 'error')
            return redirect(url_for('editar_admins'))
        cursor.execute("DELETE FROM admins WHERE id = %s", (admin_id,))
        conn.commit()
        flash('Administrador deletado com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao deletar administrador.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('editar_admins'))


# Removida rota de meta universal

@app.route('/perguntas', methods=['GET'])
def perguntas():
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    tipo_usuario = session.get('tipo_usuario')
    matricula = session.get('matricula')
    # Perguntas ativas
    if tipo_usuario == 'admin':
        cursor.execute("SELECT p.*, a.nome as admin_nome FROM perguntas p LEFT JOIN admins a ON p.id = a.id WHERE p.status = 'ativo' ORDER BY p.id DESC")
    else:
        # Para alunos: mostrar perguntas públicas OU privadas do próprio aluno OU perguntas de admins (matricula IS NULL)
        cursor.execute("SELECT p.*, a.nome as admin_nome FROM perguntas p LEFT JOIN admins a ON p.id = a.id WHERE (p.privacidade = 'publica' OR p.matricula = %s OR p.matricula IS NULL) AND p.status = 'ativo' ORDER BY p.id DESC", (matricula,))
    perguntas_respostas = cursor.fetchall()
    # Perguntas inativas (apenas admins podem ver)
    perguntas_inativas = []
    if tipo_usuario == 'admin':
        cursor.execute("SELECT p.*, a.nome as admin_nome FROM perguntas p LEFT JOIN admins a ON p.id = a.id WHERE p.status = 'inativo' ORDER BY p.id DESC")
        perguntas_inativas = cursor.fetchall()
    conn.close()
    return render_template('perguntas.html', perguntas_respostas=perguntas_respostas, perguntas_inativas=perguntas_inativas)

@app.route('/fazer_pergunta', methods=['POST'])
@login_necessario
def fazer_pergunta():
    pergunta = request.form['pergunta']
    privacidade = request.form['privacidade']
    tipo_usuario = session.get('tipo_usuario')

    # Para admins, não é necessário matricula
    matricula = None if tipo_usuario == 'admin' else session.get('matricula')
    autor_nome = session.get('login')  # ou buscar nome do aluno/admin pelo login/matricula

    conn = conexao_mysql()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO perguntas (pergunta, privacidade, matricula, autor_nome, autor_login) VALUES (%s, %s, %s, %s, %s)",
        (pergunta, privacidade, matricula, autor_nome, session.get('login'))
    )
    conn.commit()
    conn.close()
    flash('Pergunta enviada com sucesso!', 'success')
    return redirect(url_for('perguntas'))

@app.route('/excluir_pergunta/<int:pergunta_id>', methods=['POST'])
@admin_necessario
def excluir_pergunta(pergunta_id):
    justificativa = request.form['motivo_exclusao']
    conn = conexao_mysql()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE perguntas SET status='inativo', justificativa_exclusao=%s WHERE id=%s",
        (justificativa, pergunta_id)
    )
    conn.commit()
    conn.close()
    flash('Pergunta excluída com justificativa registrada!', 'success')
    return redirect(url_for('perguntas'))

@app.route('/deletar_pergunta/<int:pergunta_id>', methods=['POST'])
@admin_necessario
def deletar_pergunta(pergunta_id):
    conn = conexao_mysql()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM perguntas WHERE id=%s", (pergunta_id,))
    conn.commit()
    conn.close()
    flash('Pergunta deletada permanentemente!', 'success')
    return redirect(url_for('perguntas'))

@app.route('/responder_pergunta/<int:pergunta_id>', methods=['POST'])
@admin_necessario
def responder_pergunta(pergunta_id):
    resposta = request.form['resposta']
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM admins WHERE login = %s", (session['login'],))
    admin = cursor.fetchone()
    if not admin:
        flash('Admin não encontrado.')
        cursor.close()
        conn.close()
        return redirect(url_for('perguntas'))
    id_admin = admin['id']
    cursor.execute("UPDATE perguntas SET resposta=%s, id=%s WHERE id=%s", (resposta, id_admin, pergunta_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Resposta enviada!', 'success')
    return redirect(url_for('perguntas'))

@app.route('/alterar_privacidade/<int:pergunta_id>', methods=['POST'])
@admin_necessario
def alterar_privacidade(pergunta_id):
    nova_privacidade = request.form['nova_privacidade']
    conn = conexao_mysql()
    cursor = conn.cursor()
    cursor.execute("UPDATE perguntas SET privacidade=%s WHERE id=%s", (nova_privacidade, pergunta_id))
    conn.commit()
    conn.close()
    flash('Privacidade da pergunta alterada com sucesso!', 'success')
    return redirect(url_for('perguntas'))

@app.route('/cadastrar_filtro', methods=['GET', 'POST'])
@admin_necessario
def cadastrar_filtros():
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        nomef = request.form['nomef']
        tipof = request.form['tipof']
        try:
            cursor.execute("INSERT INTO filtros (nome, tipo) VALUES (%s, %s)", (nomef, tipof))
            conn.commit()
            flash('Filtro cadastrado com sucesso!')
        except Exception as e:
            conn.rollback()
            flash('Erro ao cadastrar filtro.')
        return redirect(url_for('cadastrar_filtros'))
    # Fetch all filtros to display in table
    cursor.execute("SELECT id, nome, tipo FROM filtros ORDER BY id DESC")
    filtros = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('cadastrar_filtros.html', filtros=filtros)

@app.route('/deletar_filtro/<int:filtro_id>', methods=['POST'])
@admin_necessario
def deletar_filtro(filtro_id):
    conn = conexao_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM filtros WHERE id = %s", (filtro_id,))
        conn.commit()
        flash('Filtro excluído com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao excluir filtro.', 'error')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('cadastrar_filtros'))

@app.route('/get_filtros/<tipo>')
@login_necessario
def get_filtros(tipo):
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nome FROM filtros WHERE tipo = %s ORDER BY nome", (tipo,))
    filtros = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([f['nome'] for f in filtros])

@app.route('/get_produtos_por_categoria/<categoria>')
@login_necessario
def get_produtos_por_categoria(categoria):
    conn = conexao_mysql()
    cursor = conn.cursor(dictionary=True)

    # Buscar produtos únicos da categoria selecionada em ambas as tabelas (despesas e arrecadações)
    if categoria == 'Eventos':
        cursor.execute("SELECT DISTINCT produto FROM despesas WHERE tipo = 'Eventos' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_despesas = cursor.fetchall()
        cursor.execute("SELECT DISTINCT produto FROM arrecadacoes WHERE tipo = 'Eventos' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_arrecadacoes = cursor.fetchall()
        # Combinar os resultados removendo duplicatas
        produtos_set = set()
        for p in produtos_despesas:
            if p['produto']:
                produtos_set.add(p['produto'])
        for p in produtos_arrecadacoes:
            if p['produto']:
                produtos_set.add(p['produto'])
        produtos = [{'produto': p} for p in sorted(produtos_set)]
    elif categoria == 'Rifas':
        cursor.execute("SELECT DISTINCT produto FROM despesas WHERE tipo = 'Rifas' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_despesas = cursor.fetchall()
        cursor.execute("SELECT DISTINCT produto FROM arrecadacoes WHERE tipo = 'Rifas' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_arrecadacoes = cursor.fetchall()
        # Combinar os resultados removendo duplicatas
        produtos_set = set()
        for p in produtos_despesas:
            if p['produto']:
                produtos_set.add(p['produto'])
        for p in produtos_arrecadacoes:
            if p['produto']:
                produtos_set.add(p['produto'])
        produtos = [{'produto': p} for p in sorted(produtos_set)]
    elif categoria == 'Produtos':
        cursor.execute("SELECT DISTINCT produto FROM despesas WHERE tipo = 'Produtos' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_despesas = cursor.fetchall()
        cursor.execute("SELECT DISTINCT produto FROM arrecadacoes WHERE tipo = 'Produtos' AND produto IS NOT NULL ORDER BY produto", (categoria,))
        produtos_arrecadacoes = cursor.fetchall()
        # Combinar os resultados removendo duplicatas
        produtos_set = set()
        for p in produtos_despesas:
            if p['produto']:
                produtos_set.add(p['produto'])
        for p in produtos_arrecadacoes:
            if p['produto']:
                produtos_set.add(p['produto'])
        produtos = [{'produto': p} for p in sorted(produtos_set)]
    else:
        # Se categoria for vazia ou inválida, buscar todos os produtos de ambas as tabelas
        cursor.execute("SELECT DISTINCT produto FROM despesas WHERE produto IS NOT NULL ORDER BY produto")
        produtos_despesas = cursor.fetchall()
        cursor.execute("SELECT DISTINCT produto FROM arrecadacoes WHERE produto IS NOT NULL ORDER BY produto")
        produtos_arrecadacoes = cursor.fetchall()
        # Combinar os resultados removendo duplicatas
        produtos_set = set()
        for p in produtos_despesas:
            if p['produto']:
                produtos_set.add(p['produto'])
        for p in produtos_arrecadacoes:
            if p['produto']:
                produtos_set.add(p['produto'])
        produtos = [{'produto': p} for p in sorted(produtos_set)]

    cursor.close()
    conn.close()
    return jsonify([p['produto'] for p in produtos])

# Rota para editar conta do admin0
@app.route('/editar_conta_admin0', methods=['POST'])
@admin_necessario
def editar_conta_admin0():
    if session.get('nivel') != 'admin0':
        flash('Acesso negado.', 'error')
        return redirect(url_for('home'))

    novo_login = request.form['novo_login']
    nova_senha = request.form['nova_senha']

    if len(nova_senha) < 6:
        flash('A senha deve ter pelo menos 6 caracteres!', 'error')
        return redirect(url_for('home'))

    conn = conexao_mysql()
    cursor = conn.cursor()

    try:
        # Verificar se o novo login já existe em outro admin
        cursor.execute("SELECT id FROM admins WHERE login = %s", (novo_login,))
        if cursor.fetchone():
            flash('Este login já está em uso por outro administrador.', 'error')
            return redirect(url_for('home'))

        # Atualizar login e senha
        cursor.execute("UPDATE admins SET login = %s, senha = %s WHERE nivel = 'admin0'", (novo_login, nova_senha))
        conn.commit()

        # Atualizar sessão
        session['login'] = novo_login

        flash('Conta atualizada com sucesso!', 'success')
    except Exception as e:
        conn.rollback()
        flash('Erro ao atualizar conta.', 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('home'))

# Rota temporária para resetar admin0 (para desenvolvimento)
@app.route('/reset_admin0')
def reset_admin0():
    conn = conexao_mysql()
    cursor = conn.cursor()
    cursor.execute("UPDATE admins SET login = 'admin0', senha = 'admin0' WHERE nivel = 'admin0'")
    conn.commit()
    cursor.close()
    conn.close()
    flash('Admin0 resetado para login: admin0, senha: admin0', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
