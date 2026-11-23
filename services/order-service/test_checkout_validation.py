
import asyncio
import getpass

from app.core.http_client import create_http_client
from app.services.checkout_client import CheckoutClient
from app.services.checkout_service import CheckoutService


async def main():
    access_token = getpass.getpass("Paste your fresh access token: ")

    client = await create_http_client()

    try:
        checkout_client = CheckoutClient(client)
        checkout_service = CheckoutService(checkout_client)

        result = await checkout_service.validate_cart(
            access_token=access_token,
            user_id=__import__("uuid").UUID(
                input("Enter your authenticated user UUID: ").strip()
            ),
        )

        print("\nCheckout validation successful")
        print("Cart ID:", result["cart_id"])
        print("Currency:", result["currency"])
        print("Subtotal (paise):", result["subtotal_minor"])
        print("Subtotal (rupees):", result["subtotal_minor"] / 100)
        print("Number of order items:", len(result["items"]))
        print("Inventory reservations required:", result["inventory_items"])

    except Exception as exc:
        print("\nCheckout validation failed:", str(exc))

    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

