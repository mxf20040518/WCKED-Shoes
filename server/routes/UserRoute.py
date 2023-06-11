from flask import Blueprint, request, Response, g
from models.UserModel import \
  register_handler,\
  login_handler,\
  find_user_handler,\
  verify_email_handler,\
  send_code_handler,\
  add_to_cart_handler,\
  get_cart_handler,\
  update_item_quantity_handler,\
  checkout_cart_handler,\
  remove_discount_handler,\
  cancel_order_handler,\
  buy_it_again_handler

import datetime
from random import randint
import json
from CustomExceptions.DBException import DBException
from middleware.Authentication import authenticate_user
from settings import limiter

user_blueprint = Blueprint("users", __name__)

REMEMBER_DURATION = 24
DONT_REMEMBER_DURATION = 3

@user_blueprint.route("/login", methods=["POST"])
def login():
  email = request.json.get("email")
  password = request.json.get("password")
  remember_me = request.json.get("remember_me")
  cookie_expires = REMEMBER_DURATION if remember_me else DONT_REMEMBER_DURATION

  try:
    result = login_handler(email, password)
    resp = Response(json.dumps(result[1]), status=200, mimetype="application/json")
    resp.set_cookie(key="auth_token", value=result[0], expires=datetime.datetime.utcnow() + datetime.timedelta(hours=cookie_expires), httponly=True)
    return resp
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/jwt-login", methods=["GET"])
@authenticate_user
def jwt_login():
  token = g.token
  return Response(json.dumps(token["sub"]), status=200, mimetype="application/json")

@user_blueprint.route("/register", methods=["POST"])
def register():
  email = request.json.get("email")
  password = request.json.get("password")

  try:
    register_handler(email, password)
    return Response("Account created successfully.", status=201, mimetype="text/plain")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/logout", methods=["GET"])
@authenticate_user
def logout():
  try:
    resp = Response("Logged out successfully.", status=200, mimetype="text/plain")
    resp.set_cookie("auth_token", "", expires=0)
    return resp
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/find", methods=["POST"])
def find_user():
  email = request.json.get("email")

  try:
    user_data = find_user_handler(email)
    return Response(json.dumps(user_data), status=200, mimetype="application/json")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/send-code", methods=["POST"])
@limiter.limit("500 per 5 minutes")
def send_code():
  email = request.json.get("email")
  code = "".join([str(randint(1, 9)) for _ in range(4)])

  try:
    send_code_handler(email, code)
    return Response(code, status=201, mimetype="text/plain")
    # return Response("Code sent.", status=201, mimetype="application/json") Will be used when email sending works
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/verify-email", methods=["POST"])
def verify_email():
  code = request.json.get("code")
  email = request.json.get("email")

  try:
    verify_email_handler(email, code)
    return Response("Email verified.", status=200, mimetype="text/plain")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")
  
@user_blueprint.route("/cart", methods=["GET"])
@authenticate_user
def get_cart():
  try:
    token = g.token
    cart = get_cart_handler(token["sub"]["id"])
    return Response(json.dumps(cart), status=200, mimetype="application/json")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/cart/<product_id>/<size>/<quantity>", methods=["POST"])
@authenticate_user
def add_to_cart(product_id, size, quantity):
  try:
    token = g.token
    result = add_to_cart_handler(token["sub"]["id"], product_id, size, (int)(quantity))
    resp = Response(json.dumps(result["user_data"]), status=200, mimetype="application/json")
    resp.set_cookie(key="auth_token", value=result["token"], expires=datetime.datetime.utcnow() + datetime.timedelta(hours=DONT_REMEMBER_DURATION), httponly=True)
    return resp
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")
  except ValueError:
    return Response("Invalid quantity.", status=400, mimetype="text/plain")
  
@user_blueprint.route("/cart/<product_id>/<size>/<quantity>", methods=["PUT", "DELETE"])
@authenticate_user
def update_item_quantity(product_id, size, quantity):
  try:
    token = g.token
    updated_cart = update_item_quantity_handler(token["sub"]["id"], product_id, size, int(quantity))
    resp = Response(json.dumps({"cart": updated_cart["cart"], "user_data": updated_cart["user_data"]}), status=200 if updated_cart["valid"] else 400, mimetype="application/json")
    resp.set_cookie(key="auth_token", value=updated_cart["token"], expires=datetime.datetime.utcnow() + datetime.timedelta(hours=DONT_REMEMBER_DURATION), httponly=True)
    return resp
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")
  except ValueError:
    return Response("Invalid quantity.", status=400, mimetype="text/plain")
  
@user_blueprint.route("/cart/checkout", methods=["POST"])
@authenticate_user
def checkout_cart():
  try:
    order_details = request.get_json()
    token = g.token
    details = checkout_cart_handler(token["sub"]["id"], order_details)
    resp = Response(json.dumps({"id": details["id"]}), status=201, mimetype="application/json")
    resp.set_cookie(key="auth_token", value=details["token"], expires=datetime.datetime.utcnow() + datetime.timedelta(hours=DONT_REMEMBER_DURATION), httponly=True)
    return resp
  except DBException as e:
    if e.data is not None: return Response(json.dumps(e.data), status=e.status_code, mimetype="application/json")
    else: return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/discount/<code_name>", methods=["DELETE"])
@authenticate_user
def remove_discount():
  try:
    token = g.token
    remove_discount_handler(token["sub"]["id"])
    return Response(f"Discount code was removed.")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")

@user_blueprint.route("/cancel-order/<order_id>", methods=["DELETE"])
@authenticate_user
def cancel_order(order_id):
  try:
    token = g.token
    cancel_order_handler(order_id, token["sub"]["id"])
    return Response(f"Order was successfully cancelled.", status=200, mimetype="text/plain")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")
  
@user_blueprint.route("/buy-it-again", methods=["GET"])
@authenticate_user
def buy_it_again():
  limit = request.args.get("limit", "", str)

  if limit == "":
    return Response("Limit is not specified.", status=400, mimetype="text/plain")

  try:
    token = g.token
    products = buy_it_again_handler(token["sub"]["id"], (int)(limit))
    return Response(json.dumps(products), status=200, mimetype="application/json")
  except DBException as e:
    return Response(e.message, status=e.status_code, mimetype="text/plain")
  except ValueError:
    return Response("'limit' is not a number.", status=400, mimetype="text/plain")