
import os
import psycopg
import json
import urllib.request
import urllib.error
import random
import time

from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')

# Palavras-chave que ativam a automação
PALAVRAS_CHAVE = [
    'quero',
    'gostei',
    'quero o link',
    'eu quero',
    'link',
    'me envia',
    'manda o link',
    'me manda',
    'tenho interesse',
    'envia pra mim'
]


# Respostas públicas aleatórias
RESPOSTAS_PUBLICAS = [
    'Oi! Te enviamos os detalhes pelo Direct!',
    'Olá! Dá uma olhadinha no seu Direct!',
    'Oba! Confira seu Direct, enviamos tudo por lá!',
    'Oi! Acabei de te enviar uma mensagem no Direct!'
]


# Produtos divulgados
PRODUTOS = [
    {
        'nome': 'Climatizador Industrial 70L',
        'link': 'https://s.shopee.com.br/7fbi3lyHLz'
    },
    {
        'nome': 'Mini Umidificador Portátil',
        'link': 'https://meli.la/2gnnPBZ'
    }
]


# Grupo de ofertas no WhatsApp
LINK_GRUPO_WHATSAPP = 'https://chat.whatsapp.com/DMGboe0eJ0ZBZdF2Y0dMuY'

DATABASE_URL = os.getenv('DATABASE_URL')


def obter_conexao():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL não configurada.')

    return psycopg.connect(DATABASE_URL)

app = Flask(__name__)


def inicializar_banco():
    with obter_conexao() as conexao:
        conexao.execute('''
            CREATE TABLE IF NOT EXISTS comentarios_processados (
                comment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            )
        ''')

        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS resposta_publica_status TEXT
            NOT NULL DEFAULT 'pendente'
        ''')

        conexao.execute('''
            ALTER TABLE comentarios_processados
            ADD COLUMN IF NOT EXISTS direct_status TEXT
            NOT NULL DEFAULT 'pendente'
        ''')

        conexao.execute('''
            UPDATE comentarios_processados
            SET
                resposta_publica_status = 'enviado',
                direct_status = 'enviado'
            WHERE status = 'enviado'
            AND resposta_publica_status = 'pendente'
            AND direct_status = 'pendente'
        ''')

        conexao.execute('''
            CREATE TABLE IF NOT EXISTS publicacoes_automacao (
                media_id TEXT PRIMARY KEY,
                ativa BOOLEAN NOT NULL DEFAULT TRUE
            )
        ''')

        conexao.execute('''
            ALTER TABLE publicacoes_automacao
            ADD COLUMN IF NOT EXISTS nome TEXT
        ''')

        conexao.execute('''
            ALTER TABLE publicacoes_automacao
            ADD COLUMN IF NOT EXISTS mensagem_direct TEXT
        ''')

        conexao.execute('''
            ALTER TABLE publicacoes_automacao
            ADD COLUMN IF NOT EXISTS link_produto TEXT
        ''')

        conexao.execute('''
            CREATE TABLE IF NOT EXISTS palavras_chave_publicacao (
                id BIGSERIAL PRIMARY KEY,
                media_id TEXT NOT NULL REFERENCES
                    publicacoes_automacao(media_id) ON DELETE CASCADE,
                palavra TEXT NOT NULL,
                UNIQUE (media_id, palavra)
            )
        ''')

        conexao.execute('''
            CREATE TABLE IF NOT EXISTS respostas_publicas_publicacao (
                id BIGSERIAL PRIMARY KEY,
                media_id TEXT NOT NULL REFERENCES
                    publicacoes_automacao(media_id) ON DELETE CASCADE,
                mensagem TEXT NOT NULL
            )
        ''')


inicializar_banco()




def registrar_comentario(comment_id):
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            INSERT INTO comentarios_processados
            (
                comment_id,
                status,
                resposta_publica_status,
                direct_status
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (comment_id) DO NOTHING
            RETURNING comment_id
            ''',
            (
                comment_id,
                'processando',
                'pendente',
                'pendente'
            )
        )

        return cursor.fetchone() is not None

def publicacao_esta_ativa(media_id):
    if not media_id:
        return False

    with obter_conexao() as conexao:
        cursor = conexao.execute(
            '''
            SELECT ativa
            FROM publicacoes_automacao
            WHERE media_id = %s
            ''',
            (media_id,)
        )

        resultado = cursor.fetchone()

        return resultado is not None and resultado[0] is True


def cadastrar_publicacao(
    media_id,
    nome,
    link_produto,
    mensagem_direct,
    palavras_chave=None,
    respostas_publicas=None
):
    palavras_chave = palavras_chave or []
    respostas_publicas = respostas_publicas or []

    with obter_conexao() as conexao:
        conexao.execute(
            '''
            INSERT INTO publicacoes_automacao (
                media_id,
                ativa,
                nome,
                link_produto,
                mensagem_direct
            )
            VALUES (%s, FALSE, %s, %s, %s)
            ''',
            (
                media_id,
                nome,
                link_produto,
                mensagem_direct
            )
        )

        for palavra in palavras_chave:
            conexao.execute(
                '''
                INSERT INTO palavras_chave_publicacao (
                    media_id,
                    palavra
                )
                VALUES (%s, %s)
                ''',
                (media_id, palavra.strip().casefold())
            )

        for mensagem in respostas_publicas:
            conexao.execute(
                '''
                INSERT INTO respostas_publicas_publicacao (
                    media_id,
                    mensagem
                )
                VALUES (%s, %s)
                ''',
                (media_id, mensagem.strip())
            )


def listar_publicacoes():
    with obter_conexao() as conexao:
        resultados = conexao.execute(
            '''
            SELECT
                p.media_id,
                p.nome,
                p.ativa,
                p.link_produto,
                p.mensagem_direct,

                COALESCE(
                    (
                        SELECT array_agg(pc.palavra ORDER BY pc.id)
                        FROM palavras_chave_publicacao pc
                        WHERE pc.media_id = p.media_id
                    ),
                    ARRAY[]::TEXT[]
                ) AS palavras_chave,

                COALESCE(
                    (
                        SELECT array_agg(rp.mensagem ORDER BY rp.id)
                        FROM respostas_publicas_publicacao rp
                        WHERE rp.media_id = p.media_id
                    ),
                    ARRAY[]::TEXT[]
                ) AS respostas_publicas

            FROM publicacoes_automacao p
            ORDER BY p.nome
            '''
        ).fetchall()

        colunas = [
            'media_id',
            'nome',
            'ativa',
            'link_produto',
            'mensagem_direct',
            'palavras_chave',
            'respostas_publicas'
        ]

        return [
            dict(zip(colunas, resultado))
            for resultado in resultados
        ]


def alterar_status_publicacao(media_id, ativa):
    with obter_conexao() as conexao:
        resultado = conexao.execute(
            '''
            UPDATE publicacoes_automacao
            SET ativa = %s
            WHERE media_id = %s
            RETURNING media_id, ativa
            ''',
            (ativa, media_id)
        ).fetchone()

        if resultado is None:
            return None

        return {
            'media_id': resultado[0],
            'ativa': resultado[1]
        }


def atualizar_publicacao(
    media_id,
    nome,
    link_produto,
    mensagem_direct
):
    with obter_conexao() as conexao:
        resultado = conexao.execute(
            '''
            UPDATE publicacoes_automacao
            SET
                nome = %s,
                link_produto = %s,
                mensagem_direct = %s
            WHERE media_id = %s
            RETURNING media_id, nome, link_produto, mensagem_direct
            ''',
            (
                nome,
                link_produto,
                mensagem_direct,
                media_id
            )
        ).fetchone()

        if resultado is None:
            return None

        return {
            'media_id': resultado[0],
            'nome': resultado[1],
            'link_produto': resultado[2],
            'mensagem_direct': resultado[3]
        }

def obter_configuracao_publicacao(media_id):
    with obter_conexao() as conexao:
        resultado = conexao.execute(
            '''
            SELECT
                nome,
                ativa,
                link_produto,
                mensagem_direct
            FROM publicacoes_automacao
            WHERE media_id = %s
            ''',
            (media_id,)
        ).fetchone()

        if resultado is None:
            return None

        return {
            'nome': resultado[0],
            'ativa': resultado[1],
            'link_produto': resultado[2],
            'mensagem_direct': resultado[3]
        }

def atualizar_palavras_chave(media_id, palavras_chave):
    palavras_normalizadas = list(dict.fromkeys(
        palavra.strip().casefold()
        for palavra in palavras_chave
        if palavra.strip()
    ))

    with obter_conexao() as conexao:
        conexao.execute(
            '''
            DELETE FROM palavras_chave_publicacao
            WHERE media_id = %s
            ''',
            (media_id,)
        )

        for palavra in palavras_normalizadas:
            conexao.execute(
                '''
                INSERT INTO palavras_chave_publicacao (
                    media_id,
                    palavra
                )
                VALUES (%s, %s)
                ''',
                (media_id, palavra)
            )


def listar_palavras_chave(media_id):
    with obter_conexao() as conexao:
        resultados = conexao.execute(
            '''
            SELECT palavra
            FROM palavras_chave_publicacao
            WHERE media_id = %s
            ORDER BY id
            ''',
            (media_id,)
        ).fetchall()

        return [resultado[0] for resultado in resultados]


def atualizar_respostas_publicas(media_id, respostas):
    respostas_filtradas = [
        resposta.strip()
        for resposta in respostas
        if resposta.strip()
    ]

    with obter_conexao() as conexao:
        conexao.execute(
            '''
            DELETE FROM respostas_publicas_publicacao
            WHERE media_id = %s
            ''',
            (media_id,)
        )

        for resposta in respostas_filtradas:
            conexao.execute(
                '''
                INSERT INTO respostas_publicas_publicacao (
                    media_id,
                    mensagem
                )
                VALUES (%s, %s)
                ''',
                (media_id, resposta)
            )


def listar_respostas_publicas(media_id):
    with obter_conexao() as conexao:
        resultados = conexao.execute(
            '''
            SELECT mensagem
            FROM respostas_publicas_publicacao
            WHERE media_id = %s
            ORDER BY id
            ''',
            (media_id,)
        ).fetchall()

        return [resultado[0] for resultado in resultados]


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

def atualizar_status_resposta_publica(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET resposta_publica_status = %s
            WHERE comment_id = %s
            ''',
            (status, comment_id)
        )

def atualizar_status_direct(comment_id, status):
    with obter_conexao() as conexao:
        conexao.execute(
            '''
            UPDATE comentarios_processados
            SET direct_status = %s
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



def responder_comentario_publicamente(comment_id, media_id):
    respostas = listar_respostas_publicas(media_id)

    if not respostas:
        print('Nenhuma resposta pública cadastrada para esta publicação.')
        return False

    url = f'https://graph.facebook.com/v27.0/{comment_id}/replies'

    mensagem = random.choice(respostas)

    payload = {
        'message': mensagem
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
            print('Resposta pública enviada com sucesso!')
            print(f'Mensagem: {mensagem}')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro ao responder comentário ({erro.code}): {detalhes}')
        return False

    except urllib.error.URLError as erro:
        print(f'Erro de conexão: {erro.reason}')
        return False




def enviar_resposta_privada(instagram_id, comment_id, media_id):
    configuracao = obter_configuracao_publicacao(media_id)

    if configuracao is None:
        print('Publicação não encontrada.')
        return False

    if not configuracao['ativa']:
        print('Automação desativada para esta publicação.')
        return False

    if not configuracao['link_produto']:
        print('Link do produto não cadastrado.')
        return False

    if not configuracao['mensagem_direct']:
        print('Mensagem privada não cadastrada.')
        return False

    url = f'https://graph.facebook.com/v27.0/{instagram_id}/messages'

    mensagem = (
        f"{configuracao['mensagem_direct']}\n\n"
        f"🛍️ Link do produto:\n"
        f"{configuracao['link_produto']}\n\n"
        f"📲 Entre também no nosso grupo:\n"
        f"{LINK_GRUPO_WHATSAPP}"
    )

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
            print('Resposta privada enviada com sucesso!')
            print(f'Retorno da API: {resultado}')
            return True

    except urllib.error.HTTPError as erro:
        detalhes = erro.read().decode('utf-8')
        print(f'Erro da API ({erro.code}): {detalhes}')
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
            if change.get('field') == 'comments':
                comment = change.get('value', {})

                comment_id = comment.get('comment_id') or comment.get('id')
                comment_text = comment.get('text')
                media = comment.get('media', {})
                media_id = media.get('id')
                user = comment.get('from', {})
                username = user.get('username')

                print(f'Conta Instagram: {instagram_id}')
                print(f'ID do comentário: {comment_id}')
                print(f'Usuário: {username}')
                print(f'Comentário: {comment_text}')
                print(f'ID da publicação: {media_id}')

                if not publicacao_esta_ativa(media_id):
                    print('Publicação não cadastrada ou automação desativada. Comentário ignorado.')
                    continue

                palavras_chave = listar_palavras_chave(media_id)

                comentario_normalizado = (
                    comment_text.strip().casefold()
                    if comment_text
                    else ''
                )

                palavra_chave_identificada = (
                    not palavras_chave
                    or any(
                        palavra in comentario_normalizado
                        for palavra in palavras_chave
                    )
                )

                if comentario_normalizado and palavra_chave_identificada:
                    print('PALAVRA-CHAVE IDENTIFICADA!')

                    if not instagram_id or not comment_id:
                        print('Dados insuficientes para processar o comentário.')
                        continue

                    if not registrar_comentario(comment_id):
                        print('Comentário já processado. Nenhuma ação será repetida.')
                        continue

                    # Tenta responder publicamente
                    sucesso_publico = responder_comentario_publicamente(
                        comment_id,
                        media_id
                    )

                    if sucesso_publico:
                        atualizar_status_resposta_publica(comment_id, 'enviado')
                    else:
                        atualizar_status_resposta_publica(comment_id, 'erro')
                        print('Falha na resposta pública. O Direct será tentado mesmo assim.')

                    # Tenta enviar o Direct até 3 vezes
                    sucesso_direct = False

                    for tentativa in range(1, 4):
                        print(f'Tentativa {tentativa} de envio do Direct.')

                        sucesso_direct = enviar_resposta_privada(
                            instagram_id,
                            comment_id,
                            media_id
                        )

                        if sucesso_direct:
                            atualizar_status_direct(comment_id, 'enviado')
                            print('Direct enviado com sucesso!')
                            break

                        if tentativa < 3:
                            print('Falha no envio. Nova tentativa em 2 segundos.')
                            time.sleep(2)

                    if sucesso_direct:
                        atualizar_status_comentario(comment_id, 'concluido')
                    else:
                        atualizar_status_direct(comment_id, 'erro')
                        atualizar_status_comentario(comment_id, 'erro')
                        print('As três tentativas falharam. Registro mantido no banco.')

                else:
                    print('Palavra-chave não identificada.')

        print('============================\n')

    return 'EVENT_RECEIVED', 200



if __name__ == '__main__':
    app.run(debug=True)
