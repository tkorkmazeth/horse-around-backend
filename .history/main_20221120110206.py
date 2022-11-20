import logging
import pydantic
from bson.objectid import ObjectId
from db_wrapper import DbWrapper
from fastapi import FastAPI, Request, File, UploadFile, Form
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import calendar
import time
import uuid
import os

pydantic.json.ENCODERS_BY_TYPE[ObjectId] = str

app = FastAPI()
db = DbWrapper()

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://horse-around.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root(info: Request):
    """
    :return: a welcoming screen
    :return:
    """
    try:
        return "Horse Around API"

    except Exception as e:
        logging.error(e)
        return e


@app.post("/user_exists/")
async def user_exists(info: Request) -> bool:
    """
    :param info: the user information to check
    :return: True if the user exists, False otherwise
    """
    try:
        req = await info.json()
        if req:
            exists = db.user_exists(req["publicAddress"])
            return exists
        else:
            return "Please provide a public address"

    except Exception as e:
        logging.error(e)
        return e


@app.get("/get_users/")
async def get_users(info: Request) -> list:
    """
    :return: a list of all the users
    """
    try:
        users = db.get_users()
        return users

    except Exception as e:
        logging.error(e)
        return e


@app.get("/get_sellers/")
async def get_sellers(info: Request) -> list:
    """
    :return: a list of all the sellers
    """
    try:
        sellers = db.get_sellers()
        return sellers

    except Exception as e:
        logging.error(e)
        return e


@app.get("/seller_exists/")
async def seller_exists(info: Request) -> bool:
    """
    :param info: the seller information to check
    :return: True if the seller exists, False otherwise
    """
    try:
        req = await info.json()
        if req:
            exists = db.seller_exists(req["publicAddress"])
            return exists
        else:
            return "Please provide a public address"

    except Exception as e:
        logging.error(e)
        return e


@app.post("/set_seller/")
@db.jwt_check_decorator
async def set_seller(info: Request) -> dict:
    """
    :param info: the user information to add
    :return: the user information that was added
    """
    try:
        req = await info.json()
        seller_info = {
            "publicAddress": req["publicAddress"],
            "name": req["name"],
            "surname": req["surname"],
            "username": req["username"],
            "email": req["email"],
            "companyLink": req["companyLink"],
        }
        seller_id = db.set_seller(seller_info)
        return seller_id

    except Exception as e:
        logging.error(e)
        return e


# @db.jwt_check_decorator
@app.post("/set_user/")
async def set_user(info: Request) -> dict:
    """
    :param info: the seller information to add
    :return: the seller information that was added
    """
    try:
        req = await info.json()
        user_info = {
            "publicAddress": req["publicAddress"],
            "nonce": 0,
            "name": "",
            "surname": "",
            "username": f"{req['publicAddress'][0:5]}..{req['publicAddress'][-3:]}",  # unique
            "bio": "",
            "image": "https://cdn3.iconfinder.com/data/icons/vector-icons-6/96/256-512.png",
            "location": "",
            "registrationDate": req["registrationDate"],
            "userType": "Creator",
            "private": False,
            "notifications": [],
            "myHorses": [],
            "soldHorses": [],
            "myBids": [],
            "favorites": [],
        }

        # Upload image to Uploadcare and return the image public link
        """
        if req["image"]:
            user_info["image"] = db.profile_image_upload(req["image"])
        """

        user_id = db.set_user(user_info)
        return user_id

    except Exception as e:
        logging.error(e)
        return e


@app.post("/update_user/")
async def update_user(
    file: UploadFile = File(None),
    token: str = Form(""),
    publicAddress: str = Form(""),
    name: str = Form(""),
    surname: str = Form(""),
    username: str = Form(""),
    bio: str = Form(""),
    location: str = Form(""),
    private: str = Form(""),
):
    """
    :param info: the user information to update
    :return: the user information that was updated
    """
    try:
        user_info = {
            "token": token,
            "publicAddress": publicAddress,
            "name": name,
            "surname": surname,
            "username": username,
            "bio": bio,
            "location": location,
            "private": private,
        }
        # Upload Image to Uploadcare and return the image public link
        if file:
            file.filename = f"{uuid.uuid4()}.png"
            contents = await file.read()  # <-- Important!

            # example of how you can save the file
            with open(f"./user_images/{file.filename}", "wb") as f:
                f.write(contents)

            image_url = db.profile_image_upload(file.filename)

            user_info["image"] = image_url

        user_id = db.update_user(user_info, user_info["token"])
        return user_id

    except Exception as e:
        logging.error(e)
        return e


@app.put("/update_user_type/")
async def update_user_type(info: Request) -> dict:
    """
    :param info: the user information to update
    :return: the user information that was updated
    """
    try:
        req = await info.json()
        user_info = {
            "publicAddress": req["publicAddress"],
            "userType": req["userType"],
        }
        user_id = db.update_user_type(user_info)
        return user_id

    except Exception as e:
        logging.error(e)
        return e


@app.put("/update_seller/")
async def update_seller(info: Request) -> dict:
    """
    :param info: the seller information to update
    :return: the seller information that was updated
    """
    try:
        req = await info.json()
        seller_info = {
            "publicAddress": req["publicAddress"],
            "name": req["name"],
            "surname": req["surname"],
            "email": req["email"],
            "companyLink": req["companyLink"],
        }
        seller_id = db.update_seller(seller_info)
        return seller_id

    except Exception as e:
        logging.error(e)
        return e


@app.post("/create_horse/")
async def create_horse(info: Request) -> dict:
    """
    :param info: the horse information to create
    :return: id of the create horse {horseId: id}
    """
    try:
        req = await info.json()
        horseId = req["id"]
        req = req["horse"]
        horse_info = {
            "publicAddress": req["publicAddress"],
            "horseId": horseId,  # represents token ID of the smart contract
            "horseName": req["horseName"],
            "birthDate": req["birthDate"],
            "age": req["age"],
            "sex": req["age"],
            "country": req["country"],
            "ownerName": req["ownerName"],
            "breederName": req["breederName"],
            "jockeyName": req["jockeyName"],
            "sireName": req["sireName"],
            "damName": req["damName"],
            "damSiblingsName": req["damSiblingsName"],
            "bonus": req["bonus"],
            "image": "https://www.clementoni.com/media/prod/tr/31811/the-horse-1500-parca-high-quality-collection_rj5qdHF.jpg",
            "horseOwnerBonus": req["horseOwnerBonus"],
            "breedingBonus": req["breedingBonus"],
            "earning": req["earning"],
            "sponsorshipEarnings": req["sponsorshipEarnings"],
            "overseasBonus": req["overseasBonus"],
            "preferenceDescription": req["preferenceDescription"],
            "totalAmount": int(req["totalAmount"]),
            "status": 2,  # 0: archive, 1: rejected, 2: collection , 3: sale, 4: auction
            "shareHolders": [],
            "auctionInfo": [],  # it is going to be filled when the horse is put on auction
            "saleInfo": [],
            "saleHistory": [],
            "achievements": [],
            "offerHistory": [],
            "winningPercent": 0,
            "winningCount": 0,
            "raceCount": 0,
        }

        horse_id = db.create_horse(horse_info)
        return horse_id

    except Exception as e:
        logging.error(e)
        return e


@app.post("/allow_horse")
async def allow_horse(info: Request) -> dict:
    """
    :param info: the horse information to add
    :return: the horse information that was added
    """
    try:
        req = await info.json()
        horse = {
            "publicAddress": req["publicAddress"],
            "horseId": req["horseId"],
        }
        # add horse to user (myHorses) & update horse
        horse = db.allow_horse(horse)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/reject_horse")
async def reject_horse(info: Request) -> dict:
    """
    :param info: the horse information to reject
    :return: the horse information that was rejected
    """
    try:
        req = await info.json()
        horseId = req["horseId"]
        horse = db.reject_horse(horseId)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/update_account_settings/")
async def update_account_settings(info: Request) -> dict:
    """
    :param info: the seller information to update
    :return: the seller information that was updated
    """
    try:
        req = await info.json()
        account_settings = {
            "publicAddress": req["publicAddress"],
            "notifications": req["notifications"],
        }
        db.update_account_settings(account_settings)
        return True

    except Exception as e:
        logging.error(e)
        return e


@app.post("/put_on_sale")
async def put_on_sale(info: Request) -> dict:
    """
    :param info: the horse information to put on sale
    :return: the horse information that was put on sale
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        token = req["token"]
        sale_info = {
            "sellerAddress": public_address,
            "price": req["price"],
            "ps": int(req["ps"]),
            "totalAmount": int(req["totalAmount"]),
            "signature": req["signature"],
            "nonce": req["nonce"],
        }
        # add horse to user (myHorses) & supdate horse
        horse = db.put_on_sale(int(horse_id), public_address, sale_info, token)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/buy_horse")
async def buy_horse(info: Request) -> dict:
    """
    :param info: the horse information to buy
    :return: the horse information that was bought
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        buyer_public_address = req["buyerAddress"]  # buyer
        seller_public_address = req["sellerAddress"]  # seller
        price = req["price"]
        ps = int(req["ps"])
        totalAmount: int(req["totalAmount"]) - ps
        saleId = req["saleId"]

        # add horse to user (myHorses) & update horse
        horse = db.buy_horse(
            int(horse_id),
            buyer_public_address,
            seller_public_address,
            price,
            ps,
            totalAmount,
            saleId,
        )
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/remove_from_sale")
async def remove_from_sale(info: Request) -> dict:
    """
    :param info: the horse information to remove from sale
    :return: the horse information that was removed from sale
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        # add horse to user (myHorses) & supdate horse
        horse = db.remove_from_sale(int(horse_id), public_address)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/put_on_auction")
async def put_on_auction(info: Request) -> dict:
    """
    :param info: the horse information to put on auction
    :return: the horse information that was put on auction
    """
    try:
        req = await info.json()

        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        auction_info = {
            "reservedPrice": req["reservedPrice"],
            "status": "active",
            "openingBid": req["openingBid"],
            "duration": int(req["duration"]) * 60 * 60 * 24,  # convert days to seconds
            "startingDate": calendar.timegm(time.gmtime()),
            "highestBid": "0",
            "highestBidder": "",
            "ps": "100",
            "signature": req["signature"],
            "nonce": req["nonce"],
            "sellerAddress": req["publicAddress"],
            "deadline": req["deadline"],
            "bidHistory": [],
        }

        horse = db.put_on_auction(int(horse_id), public_address, auction_info)
        return horse

    except Exception as e:
        logging.error(e)
        return e


@app.post("/end_auction")
async def end_auction(info: Request) -> dict:
    """
    :param info: the horse information to end auction
    :return: the horse information that was ended auction
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        buyer = req["buyer"]
        seller = req["seller"]
        token = req["token"]
        horse = db.end_auction(int(horse_id), buyer, seller, token)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/remove_from_auction")
async def remove_from_auction(info: Request) -> dict:
    """
    :param info: the horse information to remove from auction
    :return: the horse information that was removed from auction
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        horse = db.remove_from_auction(int(horse_id), public_address)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/place_a_bid")
async def place_a_bid(info: Request) -> dict:
    """
    :param info: the horse information to place a bid
    :return: the horse information that was placed a bid
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        bid_info = {
            "bidAmount": req["bidAmount"],
        }

        horse = db.place_a_bid(int(horse_id), public_address, bid_info)
        return horse

    except Exception as e:
        logging.error(e)
        return e


@app.post("/make_offer")
async def make_offer(info: Request) -> dict:
    """
    :param info: the horse information to place a bid
    :return: the horse information that was placed a bid
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        offer_info = {
            "offerAmount": req["offerAmount"],
            "ps": "100",
        }

        horse = db.make_offer(int(horse_id), public_address, offer_info)
        return horse

    except Exception as e:
        logging.error(e)
        return e


@app.post("/cancel_a_bid")
async def cancel_a_bid(info: Request) -> dict:
    """
    :param info: the horse information to cancel a bid
    :return: the horse information that was canceled a bid
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        token = req["token"]
        horse = db.cancel_a_bid(int(horse_id), public_address, token)
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/accept_a_bid")
async def accept_a_bid(info: Request) -> dict:
    """
    :param info: the horse information to accept a bid
    :return: the horse information that was accepted a bid
    """
    try:
        req = await info.json()
        horse_id = req["horseId"]
        public_address = req["publicAddress"]
        buyer_address = req["buyerAddress"]  # seller
        bid_amount = req["bidAmount"]

        horse = db.accept_a_bid(
            int(horse_id), public_address, buyer_address, bid_amount
        )
        return horse
    except Exception as e:
        logging.error(e)
        return e


@app.post("/get_user/")
async def get_user(info: Request) -> dict:
    """
    :param info: the user information to get
    :return: the user information that was requested
    """
    try:
        req = await info.json()
        user_info = {
            "publicAddress": req["publicAddress"],
        }
        user = db.get_user(user_info)
        return user

    except Exception as e:
        logging.error(e)
        return e

    """
    :param token: the token of the user
    """
    try:
        req = await info.json()
        response = db.verify(req["token"])
        return response

    except Exception as e:
        logging.error(e)
        return e


@app.post("/user_check")
async def user_check(info: Request):
    """
    :param publicAddress: the public address of the user
    """
    try:
        req = await info.json()
        user_check = db.user_check(req["publicAddress"])

        return user_check

    except Exception as e:
        logging.error(e)
        return e


@app.post("/horse_check")
async def horse_check(info: Request):
    """
    :param horseId: the horseId of the horse
    """
    try:
        req = await info.json()
        horse_check = db.horse_exists(req["horseId"])

        return horse_check

    except Exception as e:
        logging.error(e)
        return e


@app.post("/get_horse/")
async def get_horse(info: Request) -> dict:
    """
    :param info: the horse information to get
    :return: the horse information that was requested
    """
    try:
        req = await info.json()

        horse = db.get_horse(req["horseId"])
        return horse

    except Exception as e:
        logging.error(e)
        return e


@app.post("/get_horse_by_sale/")
async def get_horse(info: Request) -> dict:
    """
    :param info: the horse information to get
    :return: the horse information that was requested
    """
    try:
        req = await info.json()

        horse = db.get_horse_by_sale_id(req["horseId"], req["saleId"])
        return horse

    except Exception as e:
        logging.error(e)
        return e


@app.get("/get_horses/")
async def get_horses(info: Request) -> dict:
    """
    :return: the horse information that was requested
    """
    try:
        horses = db.get_horses()
        return horses

    except Exception as e:
        logging.error(e)
        return e


@app.post("/users/signature")
async def users_signature(info: Request):
    """
    :param publicAddress: the public address of the user
    """
    try:
        req = await info.json()
        response = db.users_signature(req["publicAddress"], req["signature"])
        return response

    except Exception as e:
        return e


@app.post("/verify")
async def verify(info: Request):
    """
    :param token: the token of the user
    """
    try:
        req = await info.json()
        response = db.verify(req["token"])
        return response

    except Exception as e:
        return e


@app.get("/get_emails")
# @db.jwt_check_decorator


async def get_emails(info: Request):
    """
    :param token: the token of the user
    """
    try:
        emails = db.get_email_subscription_list()
        return emails

    except Exception as e:
        return e


@app.post("/set_email")
# @db.jwt_check_decorator


async def set_email(info: Request):
    """
    :param token: the token of the user
    """
    try:
        req = await info.json()
        response = db.add_email_subscription(req["email"])
        return response

    except Exception as e:
        return e


# Testing the API Rate Limit Function
@app.get("/rate_limit")
async def rate_limit(info: Request):
    """
    :param publicAddress: the public address of the user
    """
    try:
        user_ip = info.client.host
        response = db.ip_rate_limit(user_ip)

        if response.status_code == 200:
            return True
        else:
            return False

    except Exception as e:
        return e


@app.post("/upload_file")
async def create_upload_file(file: UploadFile = File(...), token: str = Form(...)):
    try:

        file.filename = f"{uuid.uuid4()}.png"
        contents = await file.read()  # <-- Important!

        # example of how you can save the file
        with open(f"./user_images/{file.filename}", "wb") as f:
            f.write(contents)

        image_url = db.profile_image_upload(file.filename)

        return {"filename": file.filename, "image_url": image_url, "token": token}

    except Exception as e:
        return e
