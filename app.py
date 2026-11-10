import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect

app = Flask(__name__)
DB = "Sales.db"


# ---------- database ----------
def run(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(sql, params)
        con.commit()
        rows = cur.fetchall()
    finally:
        con.close()
    return rows


def create_tables():
    run("""CREATE TABLE IF NOT EXISTS Categories (
            catCode INTEGER PRIMARY KEY,
            catName TEXT,
            catDesc TEXT)""")
    run("""CREATE TABLE IF NOT EXISTS Products (
            prodID INTEGER PRIMARY KEY,
            catCode INTEGER,
            prodName TEXT,
            prodPrice REAL,
            FOREIGN KEY (catCode) REFERENCES Categories(catCode))""")
    run("""CREATE TABLE IF NOT EXISTS Sales (
            saleRN INTEGER PRIMARY KEY AUTOINCREMENT,
            prodID INTEGER,
            saleDate TEXT,
            saleQty INTEGER,
            saleStat TEXT,
            FOREIGN KEY (prodID) REFERENCES Products(prodID))""")


def add_amounts(rows):
    # rows: saleRN, prodID, prodName, saleDate, saleQty, saleStat, prodPrice
    result = []
    for r in rows:
        if r[5] == "Cancelled":
            amount = 0
        else:
            amount = r[4] * r[6]
        result.append([r[0], r[1], r[2], r[3], r[4], r[5], amount])
    return result


def today():
    return datetime.now().strftime("%m/%d/%Y")


# ---------- menu ----------
@app.route("/")
def index():
    return render_template("index.html")


# ---------- categories ----------
@app.route("/categories")
def categories():
    rows = run("SELECT * FROM Categories ORDER BY catCode")
    error = request.args.get("error")
    return render_template("categories.html", rows=rows, error=error)


@app.route("/categories/add", methods=["GET", "POST"])
def category_add():
    if request.method == "POST":
        try:
            run("INSERT INTO Categories VALUES (?, ?, ?)",
                (request.form["catCode"], request.form["catName"],
                 request.form["catDesc"]))
        except sqlite3.IntegrityError:
            return render_template("category_add.html", error="Code already exists.")
        return redirect("/categories")
    return render_template("category_add.html", error="")


@app.route("/categories/edit/<code>", methods=["GET", "POST"])
def category_edit(code):
    if request.method == "POST":
        run("UPDATE Categories SET catName=?, catDesc=? WHERE catCode=?",
            (request.form["catName"], request.form["catDesc"], code))
        return redirect("/categories")
    c = run("SELECT * FROM Categories WHERE catCode=?", (code,))[0]
    return render_template("category_edit.html", c=c)


@app.route("/categories/delete/<code>")
def category_delete(code):
    try:
        run("DELETE FROM Categories WHERE catCode=?", (code,))
    except sqlite3.IntegrityError:
        return redirect("/categories?error=Category still has products.")
    return redirect("/categories")


# ---------- products ----------
@app.route("/products")
def products():
    rows = run("SELECT prodID, catCode, prodName, prodPrice FROM Products ORDER BY prodID")
    error = request.args.get("error")
    return render_template("products.html", rows=rows, error=error)


@app.route("/products/add", methods=["GET", "POST"])
def product_add():
    cats = run("SELECT catCode, catName FROM Categories")
    if request.method == "POST":
        try:
            run("INSERT INTO Products VALUES (?, ?, ?, ?)",
                (request.form["prodID"], request.form["catCode"],
                 request.form["prodName"], request.form["prodPrice"]))
        except sqlite3.IntegrityError:
            return render_template("product_add.html", cats=cats, error="ID already exists.")
        return redirect("/products")
    return render_template("product_add.html", cats=cats, error="")


@app.route("/products/edit/<prod_id>", methods=["GET", "POST"])
def product_edit(prod_id):
    cats = run("SELECT catCode, catName FROM Categories")
    if request.method == "POST":
        run("UPDATE Products SET catCode=?, prodName=?, prodPrice=? WHERE prodID=?",
            (request.form["catCode"], request.form["prodName"],
             request.form["prodPrice"], prod_id))
        return redirect("/products")
    p = run("SELECT * FROM Products WHERE prodID=?", (prod_id,))[0]
    return render_template("product_edit.html", p=p, cats=cats)


@app.route("/products/delete/<prod_id>")
def product_delete(prod_id):
    try:
        run("DELETE FROM Products WHERE prodID=?", (prod_id,))
    except sqlite3.IntegrityError:
        return redirect("/products?error=Product has sales records.")
    return redirect("/products")


# ---------- sales recording ----------
@app.route("/sales")
def sales():
    rows = run("SELECT saleRN, prodID, saleDate, saleQty, saleStat FROM Sales ORDER BY saleRN")
    return render_template("sales.html", rows=rows)


@app.route("/sales/add", methods=["GET", "POST"])
def sale_add():
    prods = run("SELECT prodID, prodName FROM Products")
    if request.method == "POST":
        qty = int(request.form["saleQty"])
        if qty <= 0:
            return render_template("sale_add.html", prods=prods,
                                   error="Quantity must be more than 0.")
        run("INSERT INTO Sales (prodID, saleDate, saleQty, saleStat) VALUES (?, ?, ?, ?)",
            (request.form["prodID"], request.form["saleDate"], qty, "Active"))
        return redirect("/sales")
    return render_template("sale_add.html", prods=prods, error="")


@app.route("/sales/cancel/<rn>")
def sale_cancel(rn):
    run("UPDATE Sales SET saleStat='Cancelled' WHERE saleRN=?", (rn,))
    return redirect("/sales")


# ---------- monitoring ----------
@app.route("/monitor/product")
def monitor_product():
    prod_id = request.args.get("prod_id", "")
    prod = None
    records = []
    total_qty = 0
    total_amount = 0
    error = ""
    if prod_id != "":
        found = run("""SELECT Products.prodID, Products.prodName, Products.prodPrice,
                              Categories.catName
                       FROM Products, Categories
                       WHERE Products.catCode = Categories.catCode
                       AND Products.prodID = ?""", (prod_id,))
        if len(found) == 0:
            error = "Product not found."
        else:
            prod = found[0]
            rows = run("""SELECT Sales.saleRN, Sales.prodID, Products.prodName,
                                 Sales.saleDate, Sales.saleQty, Sales.saleStat,
                                 Products.prodPrice
                          FROM Sales, Products
                          WHERE Sales.prodID = Products.prodID
                          AND Sales.prodID = ? ORDER BY Sales.saleRN""", (prod_id,))
            records = add_amounts(rows)
            for r in records:
                if r[5] != "Cancelled":
                    total_qty = total_qty + r[4]
                total_amount = total_amount + r[6]
    return render_template("monitor_product.html", prod_id=prod_id, prod=prod,
                           records=records, total_qty=total_qty,
                           total_amount=total_amount, error=error, today=today())


@app.route("/monitor/range")
def monitor_range():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    records = []
    total_qty = 0
    total_amount = 0
    if date_from != "" and date_to != "":
        rows = run("""SELECT Sales.saleRN, Sales.prodID, Products.prodName,
                             Sales.saleDate, Sales.saleQty, Sales.saleStat,
                             Products.prodPrice
                      FROM Sales, Products
                      WHERE Sales.prodID = Products.prodID
                      AND Sales.saleDate BETWEEN ? AND ?
                      ORDER BY Sales.saleRN""", (date_from, date_to))
        records = add_amounts(rows)
        for r in records:
            if r[5] != "Cancelled":
                total_qty = total_qty + r[4]
            total_amount = total_amount + r[6]
    return render_template("monitor_range.html", date_from=date_from, date_to=date_to,
                           records=records, total_qty=total_qty,
                           total_amount=total_amount, today=today())


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
