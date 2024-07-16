import json

config = {}

def get():
    return config

def set(cfg):
    global config
    config = cfg

def add(key, val):
    global config
    config[key] = val
