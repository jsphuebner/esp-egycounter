#!/usr/bin/python3

import ast
import json
import os
import re
import paho.mqtt.client as mqtt


def parse_number(payload):
    try:
        value = payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None

    if re.match(r'^-?\d+[\.,]?\d*$', value):
        return float(value.replace(",", "."))
    return None


def safe_eval_expression(expr, values):
    node = ast.parse(expr, mode='eval')

    def eval_node(n):
        if isinstance(n, ast.Expression):
            return eval_node(n.body)
        if isinstance(n, ast.BinOp):
            left = eval_node(n.left)
            right = eval_node(n.right)
            if isinstance(n.op, ast.Add):
                return left + right
            if isinstance(n.op, ast.Sub):
                return left - right
            if isinstance(n.op, ast.Mult):
                return left * right
            if isinstance(n.op, ast.Div):
                if right == 0:
                    raise ValueError("Division by zero in expression: " + expr)
                return left / right
            raise ValueError("Unsupported operator")
        if isinstance(n, ast.UnaryOp):
            val = eval_node(n.operand)
            if isinstance(n.op, ast.UAdd):
                return +val
            if isinstance(n.op, ast.USub):
                return -val
            raise ValueError("Unsupported unary operator")
        if isinstance(n, ast.Name):
            if n.id not in values:
                raise KeyError(n.id)
            return values[n.id]
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        raise ValueError("Unsupported expression element")

    return float(eval_node(node))


def on_message(client, userdata, msg):
    alias = userdata['topic_to_alias'].get(msg.topic)
    if alias is None:
        return

    number = parse_number(msg.payload)
    if number is None:
        return

    userdata['values'][alias] = number
    try:
        result = safe_eval_expression(userdata['expression'], userdata['values'])
        client.publish(userdata['result_topic'], str(result))
    except (KeyError, ValueError, SyntaxError) as ex:
        print("mqtt_math: expression not published:", ex)
        return

config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path) as config_file:
    config = json.load(config_file)

module_config = config.get('mqtt_math', {})
aliases = module_config.get('aliases', [])
expression = module_config.get('expression', '')
result_topic = module_config.get('result_topic', '')
client_id = module_config.get('client_id', 'mqtt_math')

if not aliases or not expression or not result_topic:
    raise ValueError("mqtt_math config must define aliases, expression, and result_topic")

topic_to_alias = {}
for item in aliases:
    topic = item.get('topic')
    alias = item.get('alias')
    if not topic or not alias:
        raise ValueError("Each mqtt_math alias entry needs topic and alias")
    topic_to_alias[topic] = alias

userdata = {
    'topic_to_alias': topic_to_alias,
    'expression': expression,
    'result_topic': result_topic,
    'values': {}
}

client = mqtt.Client(client_id=client_id, userdata=userdata)
client.on_message = on_message
broker_port = config['broker'].get('port', 1883)
broker_keepalive = config['broker'].get('keepalive', 60)
client.connect(config['broker']['address'], broker_port, broker_keepalive)

for topic in topic_to_alias:
    client.subscribe(topic)

client.loop_forever()
