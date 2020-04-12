#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import re

from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.api import mail

import webapp2

class LogSenderHandler(InboundMailHandler):
    def receive(self, mail_message):
        dd_mail_code = "XXXXXXXXXXXXXXXXXXXXXXXXXX_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        dd_user_email = "sitnikov.vladimir@gmail.com"
        citi = "citialerts.russia@citi"
        lower_sender = mail_message.sender.lower()
        if dd_user_email not in lower_sender and citi not in lower_sender:
            logging.warn("Parser: sender " + mail_message.sender + " is not approved")
            mail.send_mail_to_admins(sender=dd_user_email,
                                     subject="DrebeDengi parser: unable to parse email",
                                     body="sender " + mail_message.sender + " is not approved")
            return
        plaintext_bodies = mail_message.bodies('text/plain')

        res = []
        for content_type, body in plaintext_bodies:
            if body.encoding == "binary":
                # "Unknown decoding binary" happens if Content-Transfer-Encoding is set to binary
                plaintext = body.payload
                if body.charset and str(body.charset).lower() != '7bit':
                    plaintext = plaintext.decode(str(body.charset))
            else:
                # Decodes base64 and friends
                plaintext = body.decode()

            v = ""
            if citi in plaintext or citi in mail_message.sender or "www.citibank.ru" in plaintext:
                v = self.parseCitialert(plaintext)
                if v:
                    res.append(v)

            if v == "":
                logging.warning("Unable to parse mail %", plaintext)
                mail.send_mail_to_admins(sender=dd_user_email,
                           subject="DrebeDengi parser: unable to parse email",
                           body=plaintext)

        if len(res) > 0:
            mail.send_mail_to_admins(sender=dd_user_email,
                                     subject="DrebeDengi parser: " + "; ".join(res),
                                     body="Parse result:\n" + "\n".join(res))
            mail.send_mail(sender=dd_user_email,
                           to="parser@x-pro.ru",
                           subject="Please parse " + dd_mail_code,
                           body=dd_mail_code,
                           attachments=[('lines.txt', "\n".join(res))])

        logging.info("Parse result: %s", "; ".join(res))

    def parseCitialert(self, txt):
        m = re.search(ur'Покупка на сумму (?P<summ>[0-9.]+) (?P<currency>\w+) была произведена по Вашему счету \*\*\s*(?P<account>\d+)\s+Торговая точка: (?P<operation>.*?)\s*$\s+Дата операции: (?P<date>\d\d/\d\d/\d\d\d\d)', txt, re.MULTILINE)
        if m:
            return self.result(u"покупка", m.group("summ"), m.group("currency"), m.group("account"), m.group("operation"))

        m = re.search(ur'(?P<summ>[0-9.]+) (?P<currency>\w+) было списано с Вашего счета \*\* ?(?P<account>\d+)\s+Операция: (?P<operation>.*?)\s*$\s+Дата операции: (?P<date>\d\d/\d\d/\d\d\d\d)', txt, re.MULTILINE)
        if m:
            return self.result(u"списание", m.group("summ"), m.group("currency"), m.group("account"), m.group("operation"))

        m = re.search(ur'поручение по переводу денежных средств исполнено:\s+Со счета \*\* ?(?P<account>\d+)\s+Дата: (?P<date>\d\d/\d\d/\d\d\d\d)\s+Сумма: (?P<summ>[0-9.]+) (?P<currency>\w+)', txt, re.MULTILINE)
        if m:
            return self.result(u"списание", m.group("summ"), m.group("currency"), m.group("account"), u"автоплатёж")

        m = re.search(ur'на ваш счет \*\* ?(?P<account>\d+) была зачислена сумма: (?P<summ>[0-9.]+) (?P<currency>\w+)\s+Операция: (?P<operation>.*?)\s*$\s+Дата: (?P<date>\d\d/\d\d/\d\d\d\d)', txt, re.MULTILINE)
        if m:
            return self.result(u"зачисление", m.group("summ"), m.group("currency"), m.group("account"), m.group("operation"))

        return ""

    def result(self, op_type, summ, currency, account, category):
        return u"Тип: " + op_type + u"; Сумма: " + summ + " " + currency + u"; Счёт: " + account + u"; Категория: " + category


app = webapp2.WSGIApplication([LogSenderHandler.mapping()], debug=True)
