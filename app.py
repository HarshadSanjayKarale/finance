from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from cs50 import SQL
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as total from transactions WHERE id = ? GROUP BY symbol HAVING total > 0",
        session["user_id"],
    )

    cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])[0][
        "cash"
    ]

    cash = "{:.2f}".format(float(cash))
    # print('cash' ,cash)

    total_val = 0
    grand_tot = 0

    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["value"] = stock["price"] * stock["total"]
        print(stock)
        total_val += stock["value"]
        grand_tot += stock["value"]

    return render_template(
        "index.html", stocks=stocks, cash=cash, total_val=total_val, grand_tot=grand_tot
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide symbol")
        elif not shares or not shares.isdigit() or int(shares) < 1:
            return apology("must give positive integer as share")

        quote = lookup(symbol)
        if quote is None:
            return apology("symbol not found")

        price = quote["price"]
        cost = int(shares) * price
        money = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[
            0
        ]["cash"]

        if money < cost:
            return apology("not enough credits")

        db.execute(
            "UPDATE users SET cash = cash - ? WHERE id = ?;", cost, session["user_id"]
        )

        db.execute(
            "INSERT INTO transactions (id, symbol, shares, price) VALUES (?,?,?,?);",
            session["user_id"],
            symbol,
            shares,
            price,
        )

        flash(f"BOUGHT {shares} SHARES OF {symbol} FOR {usd(cost)}!")

        return redirect("/")

    else:
        return render_template("buy.html")

    return render_template("buy.html")
    # return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute(
        "select * from transactions where id = ? order by timestamp desc;",
        session["user_id"],
    )
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")  # Get the ticker symbol from the form
        if not symbol:
            return apology("Missing Symbol", 400)

        data = lookup(symbol.upper())  # Use the uppercase symbol for consistency
        if not data:
            return apology("Invalid Symbol", 400)
        data["price"] = "{:.2f}".format(data["price"])
        # print(data)

        return render_template("quote_sucess.html", data=data)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        if not request.form.get("password"):
            return apology("must provide password", 400)
        if not request.form.get("confirmation"):
            return apology("must provide confirm password", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if len(rows) != 0:
            return apology("username is occupied", 400)

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords Dont Match", 400)

        username = request.form.get("username")
        password = request.form.get("password")

        session["user_id"] = db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?);",
            username,
            generate_password_hash(password),
        )
        # print('userid', session['user_id'])

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute(
        "select symbol, sum(shares) as total_shares from transactions where id = ? group by symbol having shares > 0;",
        session["user_id"],
    )

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide symbol")
        elif not shares or not shares.isdigit() or int(shares) < 1:
            return apology("must give positive integer as share")
        else:
            shares = int(shares)

        for stock in stocks:
            if stock["symbol"] == symbol:
                if stock["total_shares"] < shares:
                    return apology("not enough shares")
                else:
                    quote = lookup(symbol)
                    if quote is None:
                        return apology("Symbol not found")
                    price = quote["price"]
                    total_sale = shares * price
                    db.execute(
                        "update users set cash = cash + ? where id = ?;",
                        total_sale,
                        session["user_id"],
                    )

                    db.execute(
                        "insert into transactions (id, symbol, shares, price) values (?, ?, ?, ?);",
                        session["user_id"],
                        symbol,
                        shares,
                        price,
                    )

                    flash(f"Sold {shares} shares of {symbol} for {usd(total_sale)}!")

                    return redirect("/")

        return apology("symbol not found")
    else:
        return render_template("sell.html", stocks=stocks)
    
if __name__ == '__main__':
    app.run(debug=True)