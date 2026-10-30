"""Outbound messaging provider adapters. Implements the OutboundMessaging port (contracts/port.yaml).

Nothing here knows about notification's models: a provider receives the port's fields and nothing else, which
is what keeps a secret from travelling by accident.
"""
