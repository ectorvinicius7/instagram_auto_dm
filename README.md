# Instagram Auto DM

Aplicação desenvolvida em Python para automatizar o envio de mensagens privadas no Instagram a partir de comentários em publicações.

O sistema utiliza a API oficial do Instagram da Meta para identificar comentários com palavras-chave específicas e enviar automaticamente uma mensagem privada ao usuário.

## Objetivo

Facilitar a interação com usuários do Instagram por meio da automação de respostas privadas, reduzindo a necessidade de atendimento manual.

## Tecnologias utilizadas

- Python
- Flask
- PostgreSQL
- API do Instagram (Meta)
- Webhooks
- Gunicorn
- Render

## Funcionalidades

- [x] Estrutura da aplicação Flask
- [x] Endpoint inicial da aplicação
- [x] Configuração e verificação do webhook da Meta
- [x] Recebimento de notificações de comentários
- [x] Identificação de comentários por palavra-chave
- [x] Integração com PostgreSQL
- [x] Registro de comentários processados para evitar duplicidade
- [x] Envio automático de mensagens privadas pelo Instagram
- [x] Aplicação hospedada no Render
- [x] Funcionamento independente do computador local

## Banco de dados

O projeto utiliza PostgreSQL para armazenar os comentários processados e evitar que o mesmo comentário seja tratado mais de uma vez.

## Variáveis de ambiente

As credenciais e configurações são armazenadas em variáveis de ambiente, evitando a exposição de informações sensíveis no código.

Principais variáveis utilizadas:

- `INSTAGRAM_ACCESS_TOKEN`
- `WEBHOOK_VERIFY_TOKEN`
- `DATABASE_URL`

## Deploy

A aplicação está hospedada na plataforma Render, permitindo que o webhook receba notificações e processe comentários mesmo quando o computador local está desligado.

## Status do projeto

Em desenvolvimento contínuo.

A aplicação já está funcionando em produção, com recebimento de comentários e envio automático de mensagens privadas. Novas funcionalidades e melhorias serão implementadas conforme a evolução do projeto.

## Autor

Desenvolvido para fins de aprendizado e aplicação prática de integração com APIs utilizando Python.