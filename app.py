
import os
import psycopg
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

DATABASE_URL = os.getenv('DATABASE_URL')


def obter_conexao():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL não configurada.')

    return psycopg.connect(DATABASE_URL)

app = Flask(__name__)


def inicializar_banco():
    with obter_conexao() as conexao:

        # Comentários já processados
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS comentarios_processados (
                comment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
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
            (comment_id, status)
            VALUES (%s, %s)
            ON CONFLICT (comment_id) DO NOTHING
            RETURNING comment_id
            ''',
            (comment_id, 'processando')
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
    url = f'https://graph.facebook.com/v27.0/{comment_id}/replies'

    dados = urlencode({
        'message': 'Obrigado por comentar! Te enviei uma mensagem no direct, confere lá!!! 😉'
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

            # Impede que o próprio bot responda
            if user_id and str(user_id) == str(instagram_id):
                print('Comentário da própria conta. Ignorado.')
                continue

            # Verifica se a publicação é comercial e está ativa
            if not publicacao_ativa(media_id):
                print('Publicação sem automação. Comentário ignorado.')
                continue

            # Verifica se existem produtos cadastrados
            produtos = obter_produtos(media_id)

            if not produtos:
                print('Nenhum produto ativo cadastrado. Comentário ignorado.')
                continue

            # Evita processar o mesmo comentário novamente
            if not registrar_comentario(comment_id):
                print('Comentário já processado. Ignorado.')
                continue

            print('PUBLICAÇÃO COMERCIAL IDENTIFICADA!')

            # Resposta pública
            sucesso_publico = responder_comentario(comment_id)

            # Mensagem privada com os produtos
            sucesso_privado = enviar_resposta_privada(
                instagram_id,
                comment_id,
                media_id
            )

            # Registra o resultado das duas operações
            if sucesso_publico and sucesso_privado:
                atualizar_status_comentario(comment_id, 'enviado')
                print('AUTOMAÇÃO CONCLUÍDA COM SUCESSO!')

            else:
                atualizar_status_comentario(comment_id, 'parcial')
                print('Atenção: uma ou mais mensagens não foram enviadas.')

        print('============================\n')

    return 'EVENT_RECEIVED', 200

