
import os
import json
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv(override=True)

token = os.getenv('INSTAGRAM_ACCESS_TOKEN')

if not token:
    print('Token não encontrado no .env')
else:
    parametros = urlencode({
        'fields': 'id,username',
        'access_token': token
    })

    url = (
        'https://graph.facebook.com/v27.0/'
        f'me/assigned_instagram_accounts?{parametros}'
    )

    try:
        with urlopen(url, timeout=20) as resposta:
            dados = json.loads(resposta.read().decode('utf-8'))

        print('Resposta da Meta:')
        print(json.dumps(dados, indent=4, ensure_ascii=False))

        contas = dados.get('data', [])

        if contas:
            print('\nConta do Instagram encontrada!')
        else:
            print('\nNenhuma conta do Instagram encontrada.')

    except HTTPError as erro:
        resposta = json.loads(erro.read().decode('utf-8'))
        print('Erro da Meta:')
        print(json.dumps(resposta, indent=4, ensure_ascii=False))

    except URLError as erro:
        print('Erro de conexão:', erro.reason)
