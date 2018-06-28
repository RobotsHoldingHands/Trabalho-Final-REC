#!/usr/bin/python
# -*- coding: utf-8 -*-

from socket import socket, AF_INET, SOCK_DGRAM
import numpy as np
import json

class Pacote():
	def __init__(self):
		self.conteudo = {}
		self.conteudo['porta_orig'] = self.conteudo['porta_dest'] = self.conteudo['seq'] = self.conteudo['ack_n'] = self.conteudo['RTT'] = None
		self.conteudo['flags'] = {'ack': 0, 'syn': 0, 'fin': 0}
		self.conteudo['dados'] = ''

	def set(self, modificacoes):
		for modificacao in modificacoes:
			if modificacao[0] in ['syn', 'fin', 'ack']:
				self.conteudo['flags'][str(modificacao[0])] = modificacao[1]
			else:
				self.conteudo[str(modificacao[0])] = modificacao[1]

	def gera_check_sum(self):
		pacote = ''
		for chave, valor in self.conteudo.items():
			pacote += str(valor)

		soma = 0
		for i in range((0), len(pacote) - 1, 2):
			op1 = ord(pacote[i])
			op2 = ord(pacote[i+1]) << 8

			soma_atual = op1 + op2

			soma = ((soma + soma_atual) & 0xffff) + ((soma + soma_atual) >> 16)

		return soma
