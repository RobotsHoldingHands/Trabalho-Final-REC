#!/usr/bin/python
# -*- coding: utf-8 -*-

import TCP
from TCP import TCP_em_UDP

tcp = TCP_em_UDP()
sock, conn = tcp.abrir_conexao('127.0.0.1', 3883)
if not sock:
	exit()

while True:
	dados = raw_input(">>")
	if dados == 'end':
		break
	
	if '*' in dados:
		dados_split = dados.split('*')
		tcp.enviar_dados(dados_split[0] * int(dados_split[1]), sock, conn[0], conn[1])
	else:
		tcp.enviar_dados(dados, sock, conn[0], conn[1])

tcp.fechar_conexao(sock, conn[0], conn[1])
