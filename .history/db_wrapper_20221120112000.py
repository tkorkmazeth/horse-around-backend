import os
import jwt
import random
import base64
import logging
import math
from dotenv import find_dotenv, load_dotenv
from datetime import datetime, timedelta, timezone

import time
from functools import wraps

import w3storage
from pyuploadcare import File, Uploadcare

from web3 import Web3
from eth_account.messages import encode_defunct
from fastapi.exceptions import HTTPException
from pymongo import MongoClient

from PIL import Image

load_dotenv(find_dotenv())


class DbWrapper:
    def __init__(self):
        self.setup()

    def setup(self) -> bool:
        """
        :return: True if connected to the MongoDB, Error otherwise
        """
        try:
            self.connection_string = os.environ.get("MONGODB_PWD")
            self.client = MongoClient(self.connection_string)
            self.web3 = Web3()

            self.storage = w3storage.API(os.environ.get("W3STORAGE_PWD"))
            self.uploadcare = Uploadcare(
                public_key=os.environ.get("UPLOADCARE_PUBLIC_KEY"),
                secret_key=os.environ.get("UPLOADCARE_SECRET_KEY"),
            )

            self.ip_rate_limit_count = 1500
            self.ip_rate_limit_time_seconds = 60

            logging.info("Connected to MongoDB. Setup has completed.")

            return True

        except Exception as e:
            logging.error(e)
            return e

    def get_database_names(self):
        """
        :return: a list of all the database names
        """
        try:
            dbs = self.client.list_database_names()

            logging.info("Database names method was called.")

            return dbs

        except Exception as e:
            logging.error(e)
            return e

    def get_database(self, db_name: str):
        """
        :param db_name: the name of the database to get
        :return: the database object
        """
        try:
            db = self.client[db_name]

            logging.info("Database method was called.")

            return db

        except Exception as e:
            logging.error(e)
            return e

    def get_collections_names(self, db_name: str):
        """
        :param db_name: the name of the database to get the collections from
        :return: a list of all the collections in the database
        """
        try:
            db = self.get_database(db_name)
            collections = db.list_collection_names()

            logging.info("Collections names method was called.")

            return collections

        except Exception as e:
            logging.error(e)
            return e

    def get_collection(self, collection_name: str):
        """
        :param db_name: the name of the database to get the collection from
        :param collection_name: the name of the collection to get
        :return: the collection object
        """
        try:
            db = self.get_database("horses")
            collection = db[collection_name]

            logging.info("Collection method was called.")

            return collection

        except Exception as e:
            logging.error(e)
            return e

    def user_exists(self, user_public_address: str):
        """
        :param user_public_address: the public address of the user to check
        :return: True if the user exists, False otherwise
        """
        try:
            collection_name = "users"

            collection = self.get_collection(collection_name)
            user = collection.find_one({"publicAddress": user_public_address})

            logging.info(user)

            if user is not None:
                return True
            else:
                return False

        except Exception as e:
            logging.error(e)
            return e

    def username_exists(self, username: str):
        """
        :param username: the username to check
        :return: True if the username exists, False otherwise
        """
        try:
            collection_name = "users"

            collection = self.get_collection(collection_name)
            user = collection.find_one({"username": username})

            if user is not None:
                return HTTPException(
                    status_code=200, detail={"message": "Username exists", "user": user}
                )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "Username does not exist"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def get_users(self):
        """
        :return: a list of all the users
        """
        try:
            collection_name = "users"

            collection = self.get_collection(collection_name)
            users = collection.find()
            users_list = [i for i in users]

            return HTTPException(
                status_code=200,
                detail={i: users_list[i] for i in range(len(users_list))},
            )

        except Exception as e:
            logging.error(e)
            return e

    def get_horses(self):
        """
        :return: a list of all the users
        """
        try:
            collection_name = "horses"

            collection = self.get_collection(collection_name)
            horses = collection.find()
            horses_list = [i for i in horses]
            print(horses_list)

            if horses_list:
                return HTTPException(
                    status_code=200,
                    detail={i: horses_list[i] for i in range(len(horses_list))},
                )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "No horses found"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def get_user(self, user_info: dict):
        """
        :param user_info: the user information to get
        :return: existing user info if exists, else does not exist
        """
        try:
            if self.user_exists(user_info["publicAddress"]):
                collection_name = "users"

                collection = self.get_collection(collection_name)
                user = collection.find_one(
                    {"publicAddress": user_info["publicAddress"]}
                )

                return HTTPException(
                    status_code=200, detail={"message": "User exists", "user": user}
                )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "Such user does not exist"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def set_user(self, user_info: dict):
        """
        :param user_info: the user information to add
        :return: the user information that was added
        """
        try:
            if self.user_exists(user_info["publicAddress"]):
                return HTTPException(
                    status_code=200, detail={"message": "User already exists"}
                )

            collection_name = "users"

            collection = self.get_collection(collection_name)
            user = collection.insert_one(user_info).inserted_id

            userInfo = collection.find_one({"_id": user})

            return HTTPException(
                status_code=200, detail={"message": "User added", "user": userInfo}
            )

        except Exception as e:
            logging.error(e)
            return e

    def update_user(self, user_info: dict, token: str):
        """
        :param user_info: the user information to update
        :param token: the token to check
        :return: the user information that was updated
        """
        try:
            if not self.user_exists(user_info["publicAddress"]):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            decoded = self.verify(token)
            if decoded is None:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Invalid token", "response": False},
                )

            if (
                decoded.detail["user"].get("publicAddress")
                != user_info["publicAddress"]
            ):
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "User is not authorized to do this operation.",
                        "response": False,
                    },
                )

            collection_name = "users"

            collection = self.get_collection(collection_name)

            # update the user
            collection.update_one(
                {"publicAddress": user_info["publicAddress"]},
                {"$set": user_info},
            )

            return HTTPException(status_code=200, detail={"message": "User updated"})

        except Exception as e:
            logging.error(e)
            return e

    def update_user_type(self, user_info: dict):
        """
        :param user_info: the user information to update
        :return: the user information that was updated
        """
        try:
            if not self.user_exists(user_info["publicAddress"]):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            collection_name = "users"

            collection = self.get_collection(collection_name)
            user = collection.update_one(
                {"public_address": user_info["publicAddress"]},
                {"$set": {"userType": user_info["userType"]}},
            )

            return HTTPException(
                status_code=200, detail={"message": "User updated", "user": user}
            )

        except Exception as e:
            logging.error(e)
            return e

    def allow_horse(self, horse_info: dict):
        """
        :param horse_info: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(horse_info["publicAddress"]):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_info["horseId"]):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "users"

            collection = self.get_collection(collection_name)
            collection.update_one(
                {"publicAddress": horse_info["publicAddress"]},
                {"$push": {"myHorses": horse_info["horseId"]}},
            )

            collection_name = "horses"
            collection = self.get_collection(collection_name)
            collection.update_one(
                {"horseId": horse_info["horseId"]}, {"$set": {"status": 2}}
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Horse added", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def reject_horse(self, horseId: str):
        """
        :param horse_info: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.horse_exists(horseId):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"

            collection = self.get_collection(collection_name)
            collection.update_one({"horseId": horseId}, {"$set": {"status": 1}})

            return HTTPException(
                status_code=200,
                detail={"message": "Horse rejected", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def put_on_sale(
        self, horse_id: int, public_address: str, sale_info: dict, token: str
    ) -> HTTPException:
        try:
            collection_name = "horses"
            collection = self.get_collection(collection_name)

            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=404,
                    detail={"message": "User does not exist", "response": False},
                )
            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=404,
                    detail={"message": "Horse does not exist", "response": False},
                )

            decoded = self.verify(token)
            if decoded is None:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Invalid token", "response": False},
                )

            if decoded.detail["user"].get("publicAddress") != public_address:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "User is not authorized to do this operation.",
                        "response": False,
                    },
                )

            # check if horse is owned by user
            horse = collection.find_one({"horseId": horse_id})
            if horse["publicAddress"] != public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User does not own horse", "response": False},
                )

            # check if horse is already on sale
            if horse["status"] == 3:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse already on sale", "response": False},
                )

            # check if horse is already on auction

            if horse["status"] == 4:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse already on auction", "response": False},
                )

            sale_info["saleId"] = len(horse["saleInfo"])

            collection.update_one(
                {"horseId": horse_id},
                {"$set": {"status": 3}, "$push": {"saleInfo": sale_info}},
            )

            collection_name = "users"
            collection = self.get_collection(collection_name)
            user = collection.find_one({"publicAddress": public_address})
            collection.update_one(
                {"publicAddress": public_address},
                {"$set": {"nonce": user["nonce"] + 1}},
            )
            print(user)

            return HTTPException(
                status_code=200,
                detail={"message": "Horse put on sale", "response": True},
            )

        except Exception as e:
            logging.error(e)
            return e

    # if this will be on production then we need to iplement update nonce function to contract
    def remove_from_sale(self, horse_id: int, public_address: str) -> HTTPException:
        try:
            collection_name = "horses"
            collection = self.get_collection(collection_name)

            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=404,
                    detail={"message": "User does not exist", "response": False},
                )
            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=404,
                    detail={"message": "Horse does not exist", "response": False},
                )
            # check if horse is owned by user
            horse = collection.find_one({"horseId": horse_id})
            if horse["publicAddress"] != public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User does not own horse", "response": False},
                )
            # check if horse is already on sale
            if horse["status"] != 3:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse not on sale", "response": False},
                )

            collection.update_one(
                {"horseId": horse_id}, {"$set": {"saleInfo": {}, "status": 2}}
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Horse removed from sale", "response": True},
            )

        except Exception as e:
            logging.error(e)
            return e

    def buy_horse(
        self,
        horse_id: int,
        buyer_public_address: str,
        seller_public_address: str,
        price: str,
        ps: int,
        totalAmount: int,
        saleId: int,
    ) -> HTTPException:
        try:
            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=404,
                    detail={"message": "Horse does not exist", "response": False},
                )
            if not self.user_exists(buyer_public_address):
                return HTTPException(
                    status_code=404,
                    detail={"message": "User does not exist", "response": False},
                )

            # Check token id owner is public address
            collection_name = "users"
            collection = self.get_collection(collection_name)
            buyer_ownerName = collection.find_one(
                {"publicAddress": buyer_public_address}
            )["username"]
            collection.update_one(
                {"publicAddress": buyer_public_address},
                {"$push": {"myHorses": horse_id}},
            )

            # remove sold horse from seller myHorses
            collection.update_one(
                {"publicAddress": seller_public_address},
                {"$pull": {"myHorses": horse_id}, "$push": {"soldHorses": horse_id}},
            )

            collection_name = "horses"
            collection = self.get_collection(collection_name)
            horse = collection.find_one({"horseId": horse_id})
            # publicAddress, seller -> buyer OK + ownerName, seller -> buyer OK +Status, 3->2 OK
            # saleInfo, will be empty OK + saleHistory, seller, buyer, date, price  OK
            #
            collection.update_one(
                {"horseId": horse_id},
                {
                    "$set": {
                        "publicAddress": buyer_public_address,
                        "ownerName": buyer_ownerName,
                        "status": 2,
                    },
                    "$push": {
                        "saleHistory": {
                            "seller": seller_public_address,
                            "buyer": buyer_public_address,
                            "price": price,
                            "ps": ps,
                            "totalAmount": totalAmount,
                            "date": datetime.now().strftime("%d/%m/%Y"),
                        },
                        "shareHolders": {
                            "publicAddress": buyer_public_address,
                            "totalNFTs": totalAmount,
                            "percentage": ps,
                        },
                    },
                },
            )

            for index, shareholder in enumerate(horse["shareHolders"]):
                if shareholder["publicAddress"] == seller_public_address:
                    if shareholder["totalNFTs"] - ps == 0:
                        collection.update_one(
                            {"horseId": horse_id},
                            {
                                "$pull": {
                                    "shareHolders": {
                                        "publicAddress": seller_public_address
                                    }
                                }
                            },
                        )
                    else:
                        collection.update_one(
                            {"horseId": horse_id},
                            {
                                "$set": {
                                    "shareHolders."
                                    + str(index)
                                    + ".percentage": shareholder["totalAmount"]
                                    - ps
                                }
                            },
                        )
                break

            for index, sales in enumerate(horse["saleInfo"]):
                if sales["saleId"] == saleId:
                    # remove sale info
                    collection.update_one(
                        {"horseId": horse_id},
                        {"$pull": {"saleInfo": {"saleId": saleId}}},
                    )
                break

            return HTTPException(
                status_code=200,
                detail={"message": "Horse bought", "response": True},
            )

        except Exception as e:
            logging.error(e)
            return e

    def put_on_auction(self, horse_id: int, public_address: str, auction_info: dict):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if horse["publicAddress"] != public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User does not own horse", "response": False},
                )
            # check if horse is already on sale
            if horse["status"] == 3:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse already on sale", "response": False},
                )
            # check if horse is already on auction
            if horse["status"] == 4:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse already on auction", "response": False},
                )
            collection.update_one(
                {"horseId": horse_id},
                {"$set": {"status": 4}, "$push": {"auctionInfo": dict(auction_info)}},
            )

            collection_name = "users"
            collection = self.get_collection(collection_name)
            user = collection.find_one({"publicAddress": public_address})
            collection.update_one(
                {"publicAddress": public_address},
                {"$set": {"nonce": user["nonce"] + 1}},
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Horse put on auction", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def remove_from_auction(self, horse_id: int, public_address: str):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if horse["publicAddress"] != public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User does not own horse", "response": False},
                )
            # check if horse not already on auction
            if horse["status"] != 4:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse not on auction", "response": False},
                )

            collection.update_one(
                {"horseId": horse_id},
                {
                    "$set": {
                        "status": 2,
                        "auctionInfo."
                        + str(len(horse["auctionInfo"]) - 1)
                        + ".status": "Ended",
                    }
                },
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Horse removed from auction", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def place_a_bid(self, horse_id: int, public_address: str, bid_info: int):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if horse["publicAddress"] == public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User is the owner of horse", "response": False},
                )
            # check if horse not already on auction
            if horse["status"] != 4:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse is not on auction", "response": False},
                )

            bid_info["bidderAddress"] = public_address
            bid_info["date"] = datetime.now().strftime("%d/%m/%Y")

            x = len(horse["auctionInfo"]) - 1

            for bid in horse["auctionInfo"][-1].get("bidHistory"):
                if bid["bidderAddress"] == public_address:
                    print("688")
                    bid_info["bidAmount"] = int(bid_info["bidAmount"]) + int(
                        bid["bidAmount"]
                    )
                    print("xy", bid_info["bidAmount"])
                    if int(bid_info["bidAmount"]) > int(
                        horse["auctionInfo"][x]["highestBid"]
                    ):
                        print("691")
                        collection.update_one(
                            {"horseId": horse_id},
                            {
                                "$set": {
                                    "auctionInfo."
                                    + str(x)
                                    + ".highestBid": str(bid_info["bidAmount"]),
                                    "auctionInfo."
                                    + str(x)
                                    + ".highestBidder": public_address,
                                }
                            },
                        )
                    print("696")
                    collection.update_one(
                        {"horseId": horse_id},
                        {
                            "$set": {
                                "auctionInfo."
                                + str(x)
                                + ".bidHistory.$[bidder].bidAmount": str(
                                    bid_info["bidAmount"]
                                )
                            }
                        },
                        array_filters=[{"bidder.bidderAddress": public_address}],
                    )
                    break
            else:
                print("703")
                if int(bid_info["bidAmount"]) > int(
                    horse["auctionInfo"][-1]["highestBid"]
                ):
                    print("705")
                    collection.update_one(
                        {"horseId": horse_id},
                        {
                            "$set": {
                                "auctionInfo."
                                + str(x)
                                + ".highestBid": str(bid_info["bidAmount"]),
                                "auctionInfo."
                                + str(x)
                                + ".highestBidder": public_address,
                            }
                        },
                    )
                print("710")
                collection.update_one(
                    {"horseId": horse_id},
                    {"$push": {"auctionInfo." + str(x) + ".bidHistory": bid_info}},
                )

            collection_name = "users"
            collection = self.get_collection(collection_name)

            user = collection.find_one({"publicAddress": public_address})

            user_bid_info = {
                "auctionId": x,
                "horseId": horse_id,
                "isClaimed": False,
                "sellerAddress": horse["publicAddress"],
                "status": "Pending",  # Pending, Accepted, Rejected
                "bidInfo": {
                    "bidAmount": str(bid_info["bidAmount"]),
                    "date": bid_info["date"],
                },
            }
            print("726")
            for index, info in enumerate(user["myBids"]):
                if info["horseId"] == horse_id:
                    print("729")
                    collection.update_one(
                        {"publicAddress": public_address},
                        {"$set": {"myBids." + str(index): user_bid_info}},
                    )
                    break
            else:
                print("736")
                collection.update_one(
                    {"publicAddress": public_address},
                    {"$push": {"myBids": user_bid_info}},
                )

            return HTTPException(
                status_code=200,
                detail={"message": "Bid placed", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def make_offer(self, horse_id: int, public_address: str, place_info: dict):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if horse["publicAddress"] == public_address:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User is the owner of horse", "response": False},
                )
            # check if horse not already on auction
            if horse["status"] != 2:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "The horse is not eligible for an offer",
                        "response": False,
                    },
                )

            place_info["date"] = datetime.now().strftime("%d/%m/%Y")

            collection.update_one(
                {"horseId": horse_id},
                {"$push": {"offerHistory": place_info}},
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Place placed", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def cancel_a_bid(self, horse_id: int, public_address: str, token: str):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            resp = self.verify(token)

            if resp is None:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Invalid token", "response": False},
                )

            if resp.detail["user"].get("publicAddress") != public_address:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "User is not authorized to cancel bid",
                        "response": False,
                    },
                )

            collection_name = "users"
            collection = self.get_collection(collection_name)

            user = collection.find_one({"publicAddress": public_address})

            # check if user has bid on horse
            for bid in user["myBids"]:
                if bid["horseId"] == horse_id:
                    auctionId = bid["auctionId"]
                    if bid["isClaimed"] == True:
                        return HTTPException(
                            status_code=401,
                            detail={
                                "message": "Bid has already been claimed",
                                "response": False,
                            },
                        )
                    collection_name = "horses"
                    collection = self.get_collection(collection_name)

                    horse = collection.find_one({"horseId": horse_id})

                    deadline = horse["auctionInfo"][auctionId]["deadline"]

                    if horse["publicAddress"] == public_address:
                        return HTTPException(
                            status_code=401,
                            detail={
                                "message": "User is the owner of horse",
                                "response": False,
                            },
                        )
                    if (
                        horse["auctionInfo"][auctionId]["highestBidder"]
                        == public_address
                    ):
                        return HTTPException(
                            status_code=401,
                            detail={
                                "message": "User is the highest bidder, you cannot claim your bid!",
                                "response": False,
                            },
                        )

                    # find bid of user in auctionInfo and remove it
                    for index, bid in enumerate(
                        horse["auctionInfo"][auctionId]["bidHistory"]
                    ):
                        if bid["bidderAddress"] == public_address:
                            collection.update_one(
                                {"horseId": horse_id},
                                {
                                    "$pull": {
                                        "auctionInfo."
                                        + str(auctionId)
                                        + ".bidHistory": bid
                                    }
                                },
                            )
                            break

                    collection_name = "users"
                    collection = self.get_collection(collection_name)

                    # set specific bid to isClaimed
                    for index, info in enumerate(user["myBids"]):
                        if info["horseId"] == horse_id:
                            # if deadline is passed, set status to rejected
                            if math.floor(datetime.now().timestamp()) > deadline:
                                collection.update_one(
                                    {"publicAddress": public_address},
                                    {
                                        "$set": {
                                            "myBids." + str(index) + ".isClaimed": True,
                                            "myBids."
                                            + str(index)
                                            + ".status": "Rejected",
                                        }
                                    },
                                )
                                break
                            else:
                                collection.update_one(
                                    {"publicAddress": public_address},
                                    {
                                        "$set": {
                                            "myBids." + str(index) + ".isClaimed": True,
                                            "myBids."
                                            + str(index)
                                            + ".status": "Cancelled",
                                        }
                                    },
                                )
                                break

                    return HTTPException(
                        status_code=200,
                        detail={"message": "Bid cancelled", "status": "success"},
                    )
            else:
                return HTTPException(
                    status_code=401,
                    detail={"message": "User has not bid on horse", "response": False},
                )

        except Exception as e:
            logging.error(e)
            return e

    def end_auction(
        self,
        horse_id: int,
        highest_bidder_public_address: str,
        seller_public_address: str,
        token: str,
    ):
        """
        :param saleInfo: the horse information to add
        :return: the horse information that was added
        """
        try:
            if not self.user_exists(highest_bidder_public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            resp = self.verify(token)

            if resp is None:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Invalid token", "response": False},
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if resp.detail["user"].get("publicAddress") != seller_public_address and (
                resp.detail["user"].get("publicAddress")
                != horse["auctionInfo"][-1]["highestBidder"]
                and (horse["auctionInfo"][-1]["deadline"] + (4 * 60))
                > math.floor(datetime.now().timestamp())
            ):
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "User is not authorized to end auction",
                        "response": False,
                    },
                )

            if horse["publicAddress"] != seller_public_address:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "That is not the owner of horse",
                        "response": False,
                    },
                )

            if horse["status"] != 4:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "The horse is not on auction",
                        "response": False,
                    },
                )

            # check if auction is over
            if horse["auctionInfo"][-1]["deadline"] > math.floor(
                datetime.now().timestamp()
            ):
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "The auction is not over yet",
                        "response": False,
                    },
                )

            # check if auction has a winner
            if horse["auctionInfo"][-1]["highestBidder"] == "":
                return HTTPException(
                    status_code=401,
                    detail={"message": "The auction has no winner", "response": False},
                )

            # check if auction is already ended
            if horse["auctionInfo"][-1]["status"] == "Ended":
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "The auction has already ended",
                        "response": False,
                    },
                )

            self.buy_horse(
                horse_id,
                highest_bidder_public_address,
                seller_public_address,
                horse["auctionInfo"][-1]["highestBid"],
            )

            # set auction to ended
            collection.update_one(
                {"horseId": horse_id},
                {
                    "$set": {
                        "auctionInfo."
                        + str(len(horse["auctionInfo"]) - 1)
                        + ".status": "Ended"
                    }
                },
            )

            # set highest bidder's isClaimed and status to claimed
            collection_name = "users"
            collection = self.get_collection(collection_name)

            user = collection.find_one({"publicAddress": highest_bidder_public_address})

            for index, info in enumerate(user["myBids"]):
                if (
                    info["horseId"] == horse_id
                    and info["auctionId"] == len(horse["auctionInfo"]) - 1
                ):
                    collection.update_one(
                        {"publicAddress": highest_bidder_public_address},
                        {
                            "$set": {
                                "myBids." + str(index) + ".isClaimed": True,
                                "myBids." + str(index) + ".status": "Accepted",
                            }
                        },
                    )
                    break

            return HTTPException(
                status_code=200,
                detail={"message": "Auction ended", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def accept_a_bid(
        self, horse_id: int, public_address: str, buyer_address: str, bid_amount: int
    ):
        """
        :return: status
        """
        try:
            if not self.user_exists(public_address):
                return HTTPException(
                    status_code=200, detail={"message": "User does not exist"}
                )

            if not self.user_exists(buyer_address):
                return HTTPException(
                    status_code=200, detail={"message": "Seller does not exist"}
                )

            if not self.horse_exists(horse_id):
                return HTTPException(
                    status_code=200, detail={"message": "Horse does not exist"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)

            horse = collection.find_one({"horseId": horse_id})

            if horse["publicAddress"] != public_address:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "User is not the owner of horse",
                        "response": False,
                    },
                )
            # check if horse not already on auction
            if horse["status"] != 4:
                return HTTPException(
                    status_code=401,
                    detail={"message": "Horse not on auction", "response": False},
                )

            collection.update_one(
                {"horseId": horse_id},
                {
                    "$set": {
                        "status": 2,
                        "publicAddress": buyer_address,
                        "auctionInfo." + str(-1) + "status": "passive",
                    },
                    "$push": {
                        "saleHistory": {
                            "seller": public_address,
                            "buyer": buyer_address,
                            "price": bid_amount,
                            "date": datetime.now().strftime("%d/%m/%Y"),
                        }
                    },
                },
            )

            collection_name = "users"
            collection = self.get_collection(collection_name)

            collection.update_one(
                {"publicAddress": public_address},
                {"$pull": {"myHorses": horse_id}},
            )

            collection.update_one(
                {"publicAddress": buyer_address},
                {"$push": {"myHorses": horse_id}},
            )

            collection.update_one(
                {"publicAddress": buyer_address},
                {"$pull": {"myBids": horse_id}},
            )

            return HTTPException(
                status_code=200,
                detail={"message": "Bid accepted", "status": "success"},
            )

        except Exception as e:
            logging.error(e)
            return e

    def seller_exists(self, seller_public_address: str):
        """
        :param seller_public_address: the public address of the seller to check
        :return: True if the seller exists, False otherwise
        """
        try:
            collection_name = "sellers"

            collection = self.get_collection(collection_name)
            seller = collection.find_one({"public_address": seller_public_address})

            if seller is not None:
                return HTTPException(
                    status_code=200,
                    detail={"message": "Seller exists", "seller": seller},
                )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "Seller does not exist"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def get_sellers(self):
        """
        :return: a list of all the sellers
        """
        try:
            collection_name = "sellers"

            collection = self.get_collection(collection_name)
            sellers = collection.find()
            sellers_list = [i for i in sellers]

            return HTTPException(
                status_code=200,
                detail={i: sellers_list[i] for i in range(len(sellers_list))},
            )

        except Exception as e:
            logging.error(e)
            return e

    def set_seller(self, seller_info: dict):
        """
        :param seller_info: the seller information to add
        :return: the seller information that was added
        """
        try:
            if self.seller_exists(seller_info["publicAddress"]):
                return HTTPException(
                    status_code=200, detail={"message": "Seller already exists"}
                )

            if self.username_exists(seller_info["username"]):
                return HTTPException(
                    status_code=200, detail={"message": "Username already exists"}
                )

            collection_name = "sellers"

            collection = self.get_collection(collection_name)
            seller = collection.insert_one(seller_info).inserted_id

            return HTTPException(
                status_code=200, detail={"message": "Seller added", "seller": seller}
            )

        except Exception as e:
            logging.error(e)
            return e

    def update_seller(self, seller_info: dict):
        """
        :param seller_info: the seller information to update
        :return: the seller information that was updated
        """
        try:
            if not self.seller_exists(seller_info["publicAddress"]):
                return "Seller does not exist!"

            collection_name = "sellers"

            collection = self.get_collection(collection_name)
            collection.update_one(
                {"public_address": seller_info["publicAddress"]}, {"$set": seller_info}
            )

            return HTTPException(
                status_code=200, detail={"message": "Seller updated", "response": True}
            )

        except Exception as e:
            logging.error(e)
            return e

    def create_horse(self, horse_info: dict):
        """
        :param horse_info: the horse information to add
        :param token: the token of the user
        :param public_address: the public address of the user
        :return: the horse information that was added
        """
        try:
            if self.horse_exists(horse_info["horseId"]):
                return HTTPException(
                    status_code=200, detail={"message": "Horse already exists"}
                )

            collection_name = "horses"
            collection = self.get_collection(collection_name)
            horse_id = collection.insert_one(horse_info).inserted_id
            horse = collection.find_one({"_id": horse_id})
            # add shareholder to horse
            collection.update_one(
                {"horseId": horse_info["horseId"]},
                {
                    "$push": {
                        "shareHolders": {
                            "publicAddress": horse_info["publicAddress"],
                            "percentage": horse_info["totalAmount"],
                        }
                    }
                },
            )

            collection_name = "users"
            collection = self.get_collection(collection_name)
            collection.update_one(
                {"publicAddress": horse_info["publicAddress"]},
                {"$push": {"myHorses": horse["horseId"]}},
            )

            return HTTPException(
                status_code=200, detail={"message": "Horse added", "horse": horse}
            )

        except Exception as e:
            logging.error(e)
            return e

    def horse_exists(self, horse_id: int):
        try:
            collection_name = "horses"

            collection = self.get_collection(collection_name)
            horse = collection.find_one({"horseId": horse_id})

            if horse is not None:
                return True
            else:
                return False

        except Exception as e:
            logging.error(e)
            return e

    def update_account_settings(self, account_settings: dict):
        try:
            collection_name = "users"
            collection = self.get_collection(collection_name)
            publicAddress = account_settings["publicAddress"]

            if not self.user_exists(publicAddress):
                return HTTPException(
                    status_code=404,
                    detail={"message": "User does not exist", "response": False},
                )
            #  set notification list of user from database
            collection.update_one(
                {"publicAddress": publicAddress},
                {"$set": {"notifications": account_settings["notifications"]}},
            )
            return HTTPException(
                status_code=200,
                detail={"message": "Account settings updated", "response": True},
            )

        except Exception as e:
            logging.error(e)
            return e

    def get_horse(self, horse_id: int):
        """
        :param horse_id: the horse information to get
        :return: existing user info if exists, else does not exist
        """
        try:
            if self.horse_exists(horse_id):
                collection_name = "horses"

                collection = self.get_collection(collection_name)
                horse = collection.find_one({"horseId": horse_id})

                return HTTPException(
                    status_code=200, detail={"message": "Horse exists", "horse": horse}
                )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "Such horse does not exist"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def get_horse_by_sale_id(self, horse_id: int, sale_id: int):
        """
        :param horse_id: the horse information to get
        :return: existing user info if exists, else does not exist
        """
        try:
            if self.horse_exists(horse_id):
                collection_name = "horses"

                collection = self.get_collection(collection_name)
                horse = collection.find_one({"horseId": horse_id})

                if horse is not None:
                    for sale in horse["saleInfo"]:
                        if sale["saleId"] == sale_id:
                            return HTTPException(
                                status_code=200,
                                detail={
                                    "message": "Horse exists",
                                    "horse": horse,
                                    "sale": sale,
                                },
                            )
                        break
                    return HTTPException(
                        status_code=404,
                        detail={"message": "Such sale does not exist"},
                    )
                else:
                    return HTTPException(
                        status_code=404, detail={"message": "Such horse does not exist"}
                    )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "Such horse does not exist"}
                )

        except Exception as e:
            logging.error(e)
            return e

    def users_signature(self, user_public_address: str, signature: str):
        try:
            userInfo = self.user_check(user_public_address)
            if userInfo.status_code == 200:
                user = userInfo.detail["user"]
                msg = f'Horse Around Authentication for {user["publicAddress"]} with nonce : {user["nonce"]}'
                message_hex = encode_defunct(text=msg)
                expectedAddress = self.web3.eth.account.recover_message(
                    message_hex, signature=signature
                )
                print(expectedAddress.lower())
                if expectedAddress.lower() == user_public_address:
                    self.update_user_nonce(user_public_address, user["nonce"] + 1)
                    token = jwt.encode(
                        {
                            "publicAddress": user_public_address,
                            "nonce": user["nonce"],
                            "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
                        },
                        os.environ.get("SECRET"),
                        algorithm="HS256",
                    )
                    return HTTPException(
                        status_code=200,
                        detail={
                            "message": "User authenticated",
                            "token": token,
                        },
                    )
                else:
                    return HTTPException(
                        status_code=401, detail={"message": "User not authenticated"}
                    )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "User not found"}
                )

        except Exception as e:
            print(e)
            return e

    def verify(self, token: str):
        try:
            decoded = jwt.decode(token, os.environ.get("SECRET"), algorithms=["HS256"])
            return HTTPException(
                status_code=200, detail={"message": "User verified", "user": decoded}
            )
        except Exception as e:
            print(e)
            return

    def user_check(self, user_public_address: str):
        """
        :param user_public_address: the user public address
        :return: the user if exists
        """
        try:
            collection_name = "users"

            collection = self.get_collection(collection_name)

            if self.user_exists(user_public_address):
                user = collection.find_one({"publicAddress": user_public_address})
                if user:
                    return HTTPException(
                        status_code=200,
                        detail={"message": "User retrieved successfully", "user": user},
                    )
                else:
                    return HTTPException(
                        status_code=404, detail={"message": "User not found"}
                    )
            else:
                return HTTPException(
                    status_code=404, detail={"message": "User not found"}
                )

        except Exception as e:
            print(e)
            return e

    def update_user_nonce(self, user_public_address: str, nonce: int):
        try:
            collection_name = "users"
            collection = self.get_collection(collection_name)

            collection.update_one(
                {"publicAddress": user_public_address}, {"$set": {"nonce": nonce}}
            )
            return HTTPException(
                status_code=200,
                detail={"message": "User nonce updated", "response": True},
            )

        except Exception as e:
            logging.error(e)
            return e

    def ip_rate_limit_decorator(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_ip = kwargs["info"].client.host
            response = self.ip_rate_limit(user_ip)

            if response.status_code == 200:
                return await func(*args, **kwargs)
            else:
                return response.detail["message"]

        return wrapper

    def ip_rate_limit(self, ip: str):
        """
        check the incoming request user ip and limit the number of requests to 10 in a minute period and reset it
        every minute to zero according to the timestamp
        """
        try:
            collection_name = "ip"
            collection = self.get_collection(collection_name)

            ip_info = collection.find_one({"ip": ip})

            if ip_info:
                if ip_info["timestamp"] < int(
                    time.time() - self.ip_rate_limit_time_seconds
                ):
                    collection.update_one(
                        {"ip": ip},
                        {"$set": {"timestamp": int(time.time()), "count": 1}},
                    )
                    return HTTPException(
                        status_code=200, detail={"message": "IP rate limit reset"}
                    )
                else:
                    if ip_info["count"] < self.ip_rate_limit_count:
                        collection.update_one(
                            {"ip": ip}, {"$set": {"count": ip_info["count"] + 1}}
                        )
                        return HTTPException(
                            status_code=200, detail={"message": "Request accepted"}
                        )
                    else:
                        return HTTPException(
                            status_code=429, detail={"message": "Too many requests"}
                        )
            else:
                collection.insert_one(
                    {"ip": ip, "timestamp": int(time.time()), "count": 1}
                )
                return HTTPException(status_code=200, detail={"message": "IP added"})

        except Exception as e:
            print(e)
            return e

    def horse_ipfs_upload(self, img_name: str):
        try:
            # Read the image and upload it to IPFS
            image_cid = self.storage.post_upload(
                img_name, open(f"./horse_images/{img_name}", "rb")
            )
            return image_cid

        except Exception as e:
            return HTTPException(
                status_code=500,
                detail={"message": "Error uploading to IPFS", "error": str(e)},
            )

    def profile_image_upload(self, img_name: str):
        try:
            # Upload the image on the server to the cloud (Uploadcare)
            with open(f"./user_images/{img_name}", "rb") as file_object:
                uc_file: File = self.uploadcare.upload(file_object, store=True)
                return uc_file.info["original_file_url"]

        except Exception as e:
            return HTTPException(
                status_code=500, detail={"message": "Image not saved", "error": e}
            )

    def horse_image_upload(self, img_name: str):
        try:
            # Upload the image on the server to the cloud (Uploadcare)
            with open(f"./horse_images/{img_name}", "rb") as file_object:
                uc_file: File = self.uploadcare.upload(file_object, store=True)
                return uc_file.info["original_file_url"]

        except Exception as e:
            return HTTPException(
                status_code=500, detail={"message": "Image not saved", "error": e}
            )

    def admin_signature(self, admin_public_address: str, signature: str):
        try:
            msg = f"Horse Around Admin Authentication for {admin_public_address}"
            message_hex = encode_defunct(text=msg)
            expectedAddress = self.web3.eth.account.recover_message(
                message_hex, signature=signature
            )
            print("expected:", expectedAddress)
            print("admin   :", admin_public_address)
            if expectedAddress == admin_public_address:
                print("hello")
                token = jwt.encode(
                    {
                        "publicAddress": admin_public_address,
                        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
                    },
                    "YEKLABS",
                    algorithm="HS256",
                )
                print("token", token)
                return HTTPException(
                    status_code=200,
                    detail={
                        "message": "Admin authenticated",
                        "token": token,
                    },
                )

            else:
                return HTTPException(
                    status_code=401, detail={"message": "Admin not authenticated"}
                )

        except Exception as e:
            return HTTPException(
                status_code=500,
                detail={"message": "Error authenticating admin", "error": str(e)},
            )

    def admin_verify(self, token: str):
        try:
            decoded = jwt.decode(token, "YEKLABS", algorithms=["HS256"])
            if decoded["publicAddress"] in self.admins:
                return True
            else:
                return False

        except Exception as e:
            print(e)
            return e

    def jwt_check_decorator(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            req = await kwargs["info"].json()

            user_token = req["token"]
            response = self.admin_verify(user_token)

            if response:
                return await func(*args, **kwargs)
            else:
                return HTTPException(
                    status_code=401,
                    detail={
                        "message": "Admin Access Required! You are not authorized to access this page!"
                    },
                )

        return wrapper

    def add_email_subscription(self, email: str):
        try:
            collection_name = "emails"
            collection = self.get_collection(collection_name)

            if not collection.find_one({"email": email}):
                collection.insert_one({"email": email})
                return HTTPException(status_code=200, detail={"message": "Email added"})
            else:
                return HTTPException(
                    status_code=200, detail={"message": "Email already exists"}
                )

        except Exception as e:
            return HTTPException(
                status_code=500,
                detail={"message": "Error adding email subscription", "error": str(e)},
            )

    def get_email_subscription_list(self):
        try:
            collection_name = "emails"
            collection = self.get_collection(collection_name)
            emails = collection.find()

            email_list = []

            for email in emails:
                email_list.append(email["email"])

            return {"emails": email_list}

        except Exception as e:
            return HTTPException(
                status_code=500,
                detail={"message": "Error getting email list", "error": str(e)},
            )
