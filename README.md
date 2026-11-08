# HomeStock AI
**Intelligent Household Inventory & Predictive Replenishment System**

A local Flask + SQLite prototype with a responsive, Pinterest-inspired dashboard.

## 1. Requirements
- Windows 10/11, macOS or Linux
- Python 3.10 or newer
- Internet connection only for Google Fonts (the app itself runs locally)

## 2. Run on Windows (VS Code)
1. Extract `HomeStock_AI.zip`.
2. Open the `HomeStock_AI` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:

   ```powershell
   py -m venv venv
   .\venv\Scripts\activate
   ```

5. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

6. Optional: copy `.env.example` to `.env` and change `SECRET_KEY`.
7. Start the application:

   ```powershell
   python app.py
   ```

8. Open **http://127.0.0.1:5000** in your browser.
9. Register an account and start adding household items.

### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 3. Included working modules
- Registration, login, password hashing and per-user inventory separation.
- Six inventory categories and product CRUD.
- Quantity, unit, minimum stock, stocked date, optional expiry date, storage location, price and notes.
- Stock consumption transactions.
- Dashboard totals, category counts, low-stock alerts and recent activity.
- Refrigerator/freezer inventory and recorded-date reminders.
- Recipe matching against food items in the user's inventory.
- Chef Mummy local inventory-aware assistant (no paid API key).
- Smart shopping list with low-stock suggestions and duplicate prevention.
- Analytics from recorded inventory and transactions.
- Image upload, validation, preview, editable review and explicit confirmation before adding.
- Responsive desktop and mobile layout.

## 4. AI scanner: important limitation
The scanner validates and accepts photos, and includes an optional integration hook for a custom YOLO model at `models/best.pt`. If that model is not present, the scanner returns a clearly labelled manual-review placeholder. It does **not** pretend to recognize products accurately without a trained model.

To enable actual product detection:
1. Create a product dataset with bounding-box annotations for the household products you want to recognize.
2. Train/fine-tune a YOLO model for those labels.
3. Install the optional package: `pip install ultralytics`.
4. Put the trained weights at `models/best.pt`.
5. Restart Flask. All results still require user review before saving.

Generic pretrained COCO labels are not enough to reliably identify exact shampoo brands, food packet names or printed expiry dates. OCR is not enabled in this starter build; add EasyOCR/Tesseract and date validation before claiming label/date extraction.

## 5. Chef Mummy
Chef Mummy is a local rule-based assistant that reads the logged-in user's refrigerator inventory and can answer supported questions about:
- Recorded ingredients
- Recipe suggestions from the included recipe collection
- Low-stock items
- Entered food dates

It is not an unrestricted LLM chatbot and does not provide authoritative food-safety decisions. A hosted LLM can be added later through a Flask backend environment variable, without exposing secrets in browser JavaScript.

## 6. Database and files
- `homestock.db` is created automatically on first run.
- Uploaded images are stored in `uploads/`.
- Back up both before moving the project.
- Delete `homestock.db` only if you intentionally want to reset all local accounts and data.

## 7. Current prototype boundaries
- Single local instance; family sharing and cloud synchronization are future work.
- Reminders are calculated when the dashboard/API is opened; browser push notifications and scheduled background delivery are not included.
- Analytics are based only on information users actually enter.
- Consumption forecasts are intentionally conservative. Reliable personalized prediction requires enough dated stock-change records.
- Purchase value is a rough recorded value (current quantity × entered unit price), not a verified spending report.
- Food date reminders do not determine whether food is safe to eat.

## 8. Troubleshooting
- **`python` not found:** try `py app.py` on Windows or install Python and enable PATH.
- **ModuleNotFoundError:** activate the virtual environment and run `pip install -r requirements.txt`.
- **Port 5000 busy:** close the other app using port 5000, or change `port=5000` near the bottom of `app.py`.
- **Want a clean demo:** register a new account and add sample products through the UI.

## 9. Security before deployment
Change `SECRET_KEY`, disable Flask debug mode, use HTTPS, configure secure cookies, add CSRF protection/rate limiting, restrict upload storage, and run behind a production WSGI server. This project is intended as a local academic/hackathon prototype, not a production-ready public service.
