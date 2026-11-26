
import os
import psycopg
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode
import random

from dotenv import load_dotenv
from flask import Flask, request, session, redirect, url_for, render_template_string

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

DATABASE_URL = os.getenv('DATABASE_URL')


def obter_conexao():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL não configurada.')

    return psycopg.connect(DATABASE_URL)

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')


def inicializar_banco():
    with obter_conexao() as conexao:

        # Comentários já processados
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS comentarios_processados (
                comment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
        ''')

        # Controle individual dos envios
        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS status_publico TEXT
        ''')

        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS status_privado TEXT
        ''')

        # Atualiza registros antigos
        conexao.execute('''
            UPDATE comentarios_processados
            SET status_publico = 'enviado',
                status_privado = 'enviado'
            WHERE status = 'enviado'
        ''')

        conexao.execute('''
            UPDATE comentarios_processados
            SET status_publico = 'revisar',
                status_privado = 'revisar'
            WHERE status IN ('parcial', 'processando')
        ''')

        # Publicações comerciais
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS publicacoes_comerciais (
                media_id TEXT PRIMARY KEY,
                ativo BOOLEAN NOT NULL DEFAULT TRUE
            )
        ''')

        # Produtos associados às publicações
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS produtos_publicacao (
                id BIGSERIAL PRIMARY KEY,
                media_id TEXT NOT NULL
                    REFERENCES publicacoes_comerciais(media_id)
                    ON DELETE CASCADE,
                nome TEXT NOT NULL,
                url TEXT NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT TRUE
            )
        ''')

        # Respostas públicas automáticas
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS respostas_publicas (
                id BIGSERIAL PRIMARY KEY,
                mensagem TEXT NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT TRUE
            )
        ''')

        # Controle da última resposta pública utilizada
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS controle_respostas (
                id INTEGER PRIMARY KEY,
                ultima_resposta_id BIGINT
                    REFERENCES respostas_publicas(id)
            )
        ''')

        conexao.execute('''
            INSERT INTO controle_respostas (id, ultima_resposta_id)
            VALUES (1, NULL)
            ON CONFLICT (id) DO NOTHING
        ''')

def cadastrar_resposta_publica(mensagem):
    with obter_conexao() as conexao:
        conexao.execute('''
            INSERT INTO respostas_publicas (mensagem)
            VALUES (%s)
        ''', (mensagem,))

def obter_resposta_publica():
    with obter_conexao() as conexao:

        # Busca a última resposta utilizada
        controle = conexao.execute('''
            SELECT ultima_resposta_id
            FROM controle_respostas
            WHERE id = 1
            FOR UPDATE
        ''').fetchone()

        ultima_resposta_id = controle[0] if controle else None

        # Busca todas as respostas públicas ativas
        respostas = conexao.execute('''
            SELECT id, mensagem
            FROM respostas_publicas
            WHERE ativo = TRUE
        ''').fetchall()

        if not respostas:
            return None

        # Evita repetir a última resposta, quando possível
        alternativas = [
            resposta for resposta in respostas
            if resposta[0] != ultima_resposta_id
        ]

        escolhida = random.choice(alternativas or respostas)

        # Registra a resposta escolhida
        conexao.execute('''
            UPDATE controle_respostas
            SET ultima_resposta_id = %s
            WHERE id = 1
        ''', (escolhida[0],))

        return escolhida[1]

def cadastrar_publicacao(media_id):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            INSERT INTO publicacoes_comerciais (media_id)
            VALUES (%s)
            ON CONFLICT (media_id) DO NOTHING
            ''',
            (media_id,)
        )

def cadastrar_produto(media_id, nome, url):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            INSERT INTO produtos_publicacao
            (media_id, nome, url)
            VALUES (%s, %s, %s)
            ''',
            (media_id, nome, url)
        )


def obter_produtos(media_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            SELECT id, nome, url
            FROM produtos_publicacao
            WHERE media_id = %s
            AND ativo = TRUE
            ''',
            (media_id,)
        )

        return cursor.fetchall()

def publicacao_ativa(media_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            SELECT ativo
            FROM publicacoes_comerciais
            WHERE media_id = %s
            ''',
            (media_id,)
        )

        resultado = cursor.fetchone()

        return resultado is not None and resultado[0] is True

def desativar_publicacao(media_id):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE publicacoes_comerciais
            SET ativo = FALSE
            WHERE media_id = %s
            ''',
            (media_id,)
        )


def ativar_publicacao(media_id):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE publicacoes_comerciais
            SET ativo = TRUE
            WHERE media_id = %s
            ''',
            (media_id,)
        )


def registrar_comentario(comment_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            INSERT INTO comentarios_processados
            (comment_id, status, status_publico, status_privado)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (comment_id) DO NOTHING
            RETURNING comment_id
            ''',
            (comment_id, 'processando', 'pendente', 'pendente')
        )

        return cursor.fetchone() is not None


def atualizar_status_comentario(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )

def atualizar_status_publico(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET status_publico = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )


def atualizar_status_privado(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET status_privado = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )

def obter_status_envios(comment_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            SELECT status_publico, status_privado
            FROM comentarios_processados
            WHERE comment_id = %s
            ''',
            (comment_id,)
        )

        return cursor.fetchone()

def remover_comentario(comment_id):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            DELETE FROM comentarios_processados
            WHERE comment_id = %s
            ''',
            (comment_id,)
        )



def enviar_resposta_privada(instagram_id, comment_id, media_id):
    produtos = obter_produtos(media_id)

    if not produtos:
        print('Nenhum produto ativo encontrado para esta publicação.')
        return False

    mensagem = 'Olá! 😊 Que bom que você se interessou!\n\n'
    mensagem += 'Confira nossos produtos:\n\n'

    for produto in produtos:
        produto_id, nome, url_produto = produto

        mensagem += f'🛍️ {nome}\n'
        mensagem += f'{url_produto}\n\n'

    mensagem += 'Aproveite! ❤️'

    url = f'https://graph.facebook.com/v27.0/{instagram_id}/messages'

    payload = {
        'recipient': {
            'comment_id': comment_id
        },
        'message': {
            'text': mensagem
        }
    }

    dados = json.dumps(payload).encode('utf-8')

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={
            'Authorization': f'Bearer {INSTAGRAM_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(requisicao) as resposta:
            resultado = json.loads(resposta.read().decode('utf-8'))
            print('Mensagem privada enviada com sucesso!')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro da API ({erro.code}): {detalhes}')
        return False

    except urllib.error.URLError as erro:
        print(f'Erro de conexão: {erro.reason}')
        return False



def responder_comentario(comment_id):
    mensagem = obter_resposta_publica()

    if not mensagem:
        print('Nenhuma resposta pública ativa cadastrada.')
        return False

    url = f'https://graph.facebook.com/v27.0/{comment_id}/replies'

    dados = urlencode({
        'message': mensagem
    }).encode('utf-8')

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={
            'Authorization': f'Bearer {INSTAGRAM_ACCESS_TOKEN}',
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(requisicao) as resposta:
            resultado = json.loads(resposta.read().decode('utf-8'))
            print('Resposta pública enviada com sucesso!')
            print(f'Mensagem enviada: {mensagem}')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro ao responder comentário ({erro.code}): {detalhes}')
        return False

    except urllib.error.URLError as erro:
        print(f'Erro de conexão: {erro.reason}')
        return False



@app.route('/')
def home():
    return 'Instagram Auto DM - Sistema funcionando!'

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        senha = request.form.get('senha')

        if not ADMIN_PASSWORD:
            return 'Senha administrativa não configurada.', 500

        if senha == ADMIN_PASSWORD:
            session['admin_logado'] = True
            return redirect(url_for('admin'))

        return 'Senha incorreta! <a href="/admin/login">Tentar novamente</a>'

    return '''
        <h2>Instagram Auto DM</h2>
        <h3>Área administrativa</h3>

        <form method="POST">
            <input
                type="password"
                name="senha"
                placeholder="Digite sua senha"
                required
            >

            <button type="submit">Entrar</button>
        </form>
    '''

@app.route('/admin')
def admin():

    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    with obter_conexao() as conexao:
        respostas = conexao.execute('''
            SELECT id, mensagem, ativo
            FROM respostas_publicas
            ORDER BY id DESC
        ''').fetchall()

    return render_template_string('''
        <h1>Instagram Auto DM</h1>
        <h2>Gerenciar respostas públicas</h2>

        <h3>Adicionar nova resposta</h3>

        <form method="POST" action="/admin/adicionar">
            <textarea
                name="mensagem"
                placeholder="Digite a resposta pública..."
                rows="4"
                required
            ></textarea>

            <br><br>

            <button type="submit">Cadastrar resposta</button>
        </form>

        <h3>Respostas cadastradas</h3>

        {% if respostas %}
            {% for resposta in respostas %}
                <hr>

                <p><strong>ID:</strong> {{ resposta[0] }}</p>

                <p><strong>Mensagem:</strong> {{ resposta[1] }}</p>

                <p>
                    <strong>Status:</strong>
                    {{ 'Ativa' if resposta[2] else 'Desativada' }}
                </p>

                <form method="POST" action="/admin/editar/{{ resposta[0] }}">
                    <textarea
                        name="mensagem"
                        rows="3"
                        required
                    >{{ resposta[1] }}</textarea>

                    <br><br>

                    <button type="submit">Salvar alteração</button>
                </form>

                <form method="POST" action="/admin/toggle/{{ resposta[0] }}">
                    <button type="submit">
                        {{ 'Desativar' if resposta[2] else 'Ativar' }}
                    </button>
                </form>

                <form
                    method="POST"
                    action="/admin/excluir/{{ resposta[0] }}"
                    onsubmit="return confirm('Tem certeza que deseja excluir esta resposta?')"
                >
                    <button type="submit">Excluir resposta</button>
                </form>

            {% endfor %}
        {% else %}
            <p>Nenhuma resposta cadastrada.</p>
        {% endif %}
    ''', respostas=respostas)



@app.route('/admin/adicionar', methods=['POST'])
def admin_adicionar():
    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    mensagem = request.form.get('mensagem', '').strip()

    if not mensagem:
        return redirect(url_for('admin'))

    cadastrar_resposta_publica(mensagem)

    return redirect(url_for('admin'))

@app.route('/admin/toggle/<int:resposta_id>', methods=['POST'])
def admin_toggle(resposta_id):
    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    with obter_conexao() as conexao:
        conexao.execute('''
            UPDATE respostas_publicas
            SET ativo = NOT ativo
            WHERE id = %s
        ''', (resposta_id,))

    return redirect(url_for('admin'))

@app.route('/admin/editar/<int:resposta_id>', methods=['POST'])
def admin_editar(resposta_id):
    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    mensagem = request.form.get('mensagem', '').strip()

    if not mensagem:
        return redirect(url_for('admin'))

    with obter_conexao() as conexao:
        conexao.execute('''
            UPDATE respostas_publicas
            SET mensagem = %s
            WHERE id = %s
        ''', (mensagem, resposta_id))

    return redirect(url_for('admin'))


@app.route('/admin/excluir/<int:resposta_id>', methods=['POST'])
def admin_excluir(resposta_id):
    if not session.get('admin_logado'):
        return redirect(url_for('admin_login'))

    with obter_conexao() as conexao:
        conexao.execute('''
            UPDATE controle_respostas
            SET ultima_resposta_id = NULL
            WHERE ultima_resposta_id = %s
        ''', (resposta_id,))

        conexao.execute('''
            DELETE FROM respostas_publicas
            WHERE id = %s
        ''', (resposta_id,))

    return redirect(url_for('admin'))


@app.route('/auth/instagram/callback')
def instagram_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f'Erro na autorização: {error}'

    if not code:
        return 'Código de autorização não recebido.', 400

    return f'Código de autorização recebido: {code}'


@app.route('/webhook', methods=['GET'])
def webhook_verification():
    verify_token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    mode = request.args.get('hub.mode')

    if mode == 'subscribe' and verify_token == WEBHOOK_VERIFY_TOKEN:
        return challenge, 200

    return 'Token de verificação inválido', 403



@app.route('/webhook', methods=['POST'])
def webhook_receive():
    data = request.get_json(silent=True)

    if not data:
        return 'Dados inválidos', 400

    print('\n===== WEBHOOK RECEBIDO =====')

    for entry in data.get('entry', []):
        instagram_id = entry.get('id')

        for change in entry.get('changes', []):

            if change.get('field') != 'comments':
                continue

            comment = change.get('value', {})

            comment_id = comment.get('comment_id') or comment.get('id')
            comment_text = comment.get('text')
            media = comment.get('media', {})
            media_id = media.get('id')
            user = comment.get('from', {})
            username = user.get('username')
            user_id = user.get('id')

            print(f'Usuário: {username}')
            print(f'Comentário: {comment_text}')
            print(f'ID da publicação: {media_id}')

            # Verifica se os dados necessários existem
            if not instagram_id or not comment_id or not media_id:
                print('Dados insuficientes. Comentário ignorado.')
                continue

            # Impede que a própria conta responda
            if user_id and str(user_id) == str(instagram_id):
                print('Comentário da própria conta. Ignorado.')
                continue

            # Verifica se a publicação comercial está ativa
            if not publicacao_ativa(media_id):
                print('Publicação pessoal ou comercial desativada. Ignorada.')
                continue

            # Evita processar o mesmo comentário novamente
            if not registrar_comentario(comment_id):
                print('Comentário já processado. Ignorado.')
                continue

            print('PUBLICAÇÃO COMERCIAL ATIVA IDENTIFICADA!')

            # Resposta pública
            sucesso_publico = responder_comentario(comment_id)

            # Mensagem privada com os produtos
            sucesso_privado = enviar_resposta_privada(
                instagram_id,
                comment_id,
                media_id
            )

            # Registra o resultado dos envios
            if sucesso_publico and sucesso_privado:
                atualizar_status_comentario(comment_id, 'enviado')
                print('AUTOMAÇÃO CONCLUÍDA COM SUCESSO!')

            else:
                atualizar_status_comentario(comment_id, 'parcial')
                print('Atenção: uma ou mais mensagens não foram enviadas.')

        print('============================\n')

    return 'EVENT_RECEIVED', 200

inicializar_banco()
