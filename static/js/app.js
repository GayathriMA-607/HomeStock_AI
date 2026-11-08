
const CATS = [
    "Pantry & Kitchen",
    "Stationery & Daily-use",
    "Cleaning & Sanitation",
    "Bathroom & Personal Care",
    "Refrigerator & Freezer",
    "Household Utilities"
];

const CAT_ICONS = ["🌾", "✎", "🫧", "🧴", "🥬", "🔋"];

const CAT_COLORS = [
    "#f5eddf",
    "#edf1f4",
    "#e8f0ec",
    "#f5e9e5",
    "#e8f0e6",
    "#f2eee4"
];

let inventory = [];
let scanDraft = [];

const $ = id => document.getElementById(id);


// ===============================
// API AND NOTIFICATIONS
// ===============================

async function api(url, opts = {}) {
    const r = await fetch(url, {
        headers: {
            "Content-Type": "application/json",
            ...(opts.headers || {})
        },
        ...opts
    });

    let d = {};

    try {
        d = await r.json();
    } catch {}

    if (!r.ok) {
        throw new Error(d.error || "Request failed");
    }

    return d;
}


function toast(s) {
    const t = $("toast");

    t.textContent = s;
    t.classList.add("show");

    setTimeout(() => t.classList.remove("show"), 2600);
}


// ===============================
// PAGE NAVIGATION AND BREADCRUMB
// ===============================

function showPage(name) {

    // Hide all pages
    document.querySelectorAll(".page").forEach(p =>
        p.classList.remove("active")
    );

    // Show selected page
    $("page-" + name).classList.add("active");

    // Update active sidebar navigation
    document.querySelectorAll(".nav-link").forEach(b =>
        b.classList.toggle("active", b.dataset.page === name)
    );

    // Update breadcrumb
    const pageNames = {
        home: "Overview",
        inventory: "My inventory",
        scanner: "AI scanner",
        food: "Fridge & freezer",
        recipes: "Recipe ideas",
        shopping: "Shopping list",
        chef: "Chef Mummy",
        analytics: "Insights",
        profile: "Profile"
    };

    $("crumbName").textContent = pageNames[name] || "Overview";

    // Close mobile sidebar
    $("sidebar").classList.remove("open");

    // Load page data
    if (name === "inventory" || name === "food") loadInventory();
    if (name === "recipes") loadRecipes();
    if (name === "shopping") loadShopping();
    if (name === "analytics") loadAnalytics();
    if (name === "home") loadOverview();
}


// Navigation click events
document.querySelectorAll(".nav-link").forEach(b =>
    b.addEventListener("click", () => showPage(b.dataset.page))
);


$("mobileMenu").onclick = () =>
    $("sidebar").classList.toggle("open");


$("todayLabel").textContent = new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short"
}).format(new Date());


// ===============================
// HELPER FUNCTION
// ===============================

function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[c]));
}


// ===============================
// INVENTORY
// ===============================

async function loadInventory() {
    try {
        inventory = await api("/api/inventory");

        renderInventory();
        renderFood();

    } catch (e) {
        toast(e.message);
    }
}


async function loadOverview() {
    try {
        const d = await api("/api/overview");

        $("statTotal").textContent = d.total_items;
        $("statLow").textContent = d.low_stock;
        $("statAlerts").textContent =
            d.alerts.filter(x => x.type !== "low").length;

        $("statShopping").textContent = d.shopping_count;

        $("categoryGrid").innerHTML = d.categories.map((c, i) => `
            <button class="category-card"
                onclick="filterCategory('${esc(c.name)}')">

                <span class="cat-art"
                    style="background:${CAT_COLORS[i]}">
                    ${CAT_ICONS[i]}
                </span>

                <span>
                    <b>${esc(c.name)}</b>
                    <small>${c.count} product${c.count === 1 ? "" : "s"}</small>
                </span>

                <span class="cat-arrow">→</span>
            </button>
        `).join("");


        $("alertList").innerHTML = d.alerts.length
            ? d.alerts.map(a => `
                <div class="alert-row">
                    <span class="alert-symbol">
                        ${a.type === "low" ? "↘" : "♧"}
                    </span>

                    <p>
                        ${esc(a.message)}
                        <small>${esc(a.type)} reminder</small>
                    </p>
                </div>
            `).join("")
            : `<div class="empty">
                All clear for now. Your home is looking good ✿
               </div>`;


        $("recentList").innerHTML = d.recent.length
            ? d.recent.map(x => `
                <div class="recent-row">
                    <span class="recent-dot"></span>

                    <div>
                        ${esc(x.name)}
                        <small>
                            ${esc(x.kind)} · ${esc(x.amount)} unit(s)
                        </small>
                    </div>
                </div>
            `).join("")
            : `<div class="empty">
                Your recent updates will appear here.
               </div>`;

    } catch (e) {
        toast(e.message);
    }
}


function filterCategory(c) {
    showPage("inventory");

    $("categoryFilter").value = c;

    renderInventory();
}


function renderInventory() {

    const q = ($("inventorySearch")?.value || "").toLowerCase();
    const cat = $("categoryFilter")?.value || "";
    const sort = $("sortFilter")?.value || "name";

    let a = inventory.filter(x =>
        x.name.toLowerCase().includes(q) &&
        (!cat || x.category === cat)
    );

    a.sort((x, y) =>
        sort === "quantity"
            ? x.quantity - y.quantity
            : sort === "expiry"
                ? (x.expiry_date || "9999").localeCompare(y.expiry_date || "9999")
                : x.name.localeCompare(y.name)
    );

    $("inventoryGrid").innerHTML = a.length
        ? a.map(productCard).join("")
        : `<div class="empty" style="grid-column:1/-1">
            No products found. Add your first household item ✿
           </div>`;
}


function productCard(x) {

    let i = CATS.indexOf(x.category);
    let low = x.quantity <= x.minimum_stock;

    return `
        <article class="product-card">

            <div class="product-art"
                style="background:${CAT_COLORS[Math.max(0, i)]}">
                ${CAT_ICONS[Math.max(0, i)]}
            </div>

            <div class="product-body">

                <h3>${esc(x.name)}</h3>

                <p>
                    ${esc(x.category)} · ${esc(x.location || "Home")}
                </p>

                <div class="product-meta">

                    <span class="qty">
                        ${x.quantity}
                        <small style="font:10px 'DM Sans';color:#9aa39b">
                            ${esc(x.unit)}
                        </small>
                    </span>

                    <span class="stock-badge ${low ? "low" : ""}">
                        ${low ? "Low stock" : "In stock"}
                    </span>

                </div>

                <div class="product-actions">
                    <button class="mini-btn"
                        onclick="consumeItem(${x.id})">
                        − Use
                    </button>

                    <button class="mini-btn"
                        onclick="editItem(${x.id})">
                        Edit
                    </button>

                    <button class="mini-btn"
                        onclick="deleteItem(${x.id})">
                        Remove
                    </button>
                </div>

            </div>
        </article>
    `;
}


function renderFood() {

    let a = inventory.filter(x =>
        x.category === "Refrigerator & Freezer"
    );

    $("foodGrid").innerHTML = a.length
        ? a.map(productCard).join("")
        : `<div class="empty" style="grid-column:1/-1">
            Your fridge is waiting for its first entry.
            Add a food item to get started.
           </div>`;

    const alerts = inventory.filter(x =>
        x.category === "Refrigerator & Freezer" && x.expiry_date
    );

    $("foodAlerts").innerHTML = alerts.length
        ? alerts.map(x => `
            <div class="alert-row">
                <span class="alert-symbol">♧</span>

                <p>
                    ${esc(x.name)}
                    <small>
                        Recorded date: ${esc(x.expiry_date)}
                        · Check the package label.
                    </small>
                </p>
            </div>
        `).join("")
        : `<div class="empty">No food dates recorded yet.</div>`;
}


// ===============================
// ADD AND EDIT PRODUCTS
// ===============================

function openAdd(cat = 0) {

    $("itemForm").reset();

    $("editId").value = "";
    $("modalTitle").textContent = "Add a product";

    $("fCategory").selectedIndex = cat;

    $("fQty").value = 1;
    $("fMin").value = 1;

    $("fStocked").value = new Date()
        .toISOString()
        .slice(0, 10);

    $("itemModal").classList.add("open");
}


function closeModal() {
    $("itemModal").classList.remove("open");
}


function editItem(id) {

    let x = inventory.find(i => i.id === id);

    if (!x) return;

    openAdd(CATS.indexOf(x.category));

    $("modalTitle").textContent = "Edit product";

    $("editId").value = id;
    $("fName").value = x.name;
    $("fCategory").value = x.category;
    $("fQty").value = x.quantity;
    $("fUnit").value = x.unit;
    $("fMin").value = x.minimum_stock;
    $("fStocked").value = x.date_stocked || "";
    $("fExpiry").value = x.expiry_date || "";
    $("fLocation").value = x.location || "";
    $("fPrice").value = x.price || 0;
    $("fNotes").value = x.notes || "";
}


$("itemForm").onsubmit = async e => {

    e.preventDefault();

    let d = {
        name: $("fName").value,
        category: $("fCategory").value,
        quantity: $("fQty").value,
        unit: $("fUnit").value,
        minimum_stock: $("fMin").value,
        date_stocked: $("fStocked").value,
        expiry_date: $("fExpiry").value,
        location: $("fLocation").value,
        price: $("fPrice").value,
        notes: $("fNotes").value
    };

    try {

        let id = $("editId").value;

        if (id) {
            await api("/api/inventory/" + id, {
                method: "PUT",
                body: JSON.stringify(d)
            });
        } else {
            await api("/api/inventory", {
                method: "POST",
                body: JSON.stringify(d)
            });
        }

        closeModal();

        toast(id ? "Product updated" : "Product added to your home");

        await loadInventory();
        await loadOverview();

    } catch (e) {
        toast(e.message);
    }
};


// ===============================
// DELETE AND CONSUME PRODUCTS
// ===============================

async function deleteItem(id) {

    if (!confirm("Remove this product from your inventory?")) return;

    try {

        await api("/api/inventory/" + id, {
            method: "DELETE"
        });

        toast("Product removed");

        await loadInventory();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


async function consumeItem(id) {

    let x = inventory.find(i => i.id === id);

    let v = prompt(
        `How much ${x.name} did you use? Current: ${x.quantity} ${x.unit}`,
        "1"
    );

    if (v === null) return;

    try {

        await api(`/api/inventory/${id}/consume`, {
            method: "POST",
            body: JSON.stringify({ amount: v })
        });

        toast("Stock usage recorded");

        await loadInventory();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


// ===============================
// ALERTS
// ===============================

async function loadAlerts() {

    try {

        let a = await api("/api/alerts");

        toast(
            a.length
                ? `${a.length} reminder(s) need attention`
                : "No reminders right now"
        );

    } catch (e) {
        toast(e.message);
    }
}


$("alertsBtn").onclick = loadAlerts;


// ===============================
// AI SCANNER
// ===============================

$("scanFile").onchange = e => {

    if (e.target.files[0]) {
        processScan(e.target.files[0]);
    }
};


$("dropZone").ondragover = e => {

    e.preventDefault();

    $("dropZone").style.background = "#eef4ed";
};


$("dropZone").ondrop = e => {

    e.preventDefault();

    $("dropZone").style.background = "";

    if (e.dataTransfer.files[0]) {
        processScan(e.dataTransfer.files[0]);
    }
};


async function processScan(file) {

    if (!file.type.startsWith("image/")) {
        return toast("Please choose an image.");
    }

    $("scanPreview").src = URL.createObjectURL(file);
    $("scanPreview").hidden = false;

    let fd = new FormData();

    fd.append("image", file);

    $("dropZone").querySelector("h3").textContent =
        "Looking at your photo…";

    try {

        let r = await fetch("/api/scanner", {
            method: "POST",
            body: fd
        });

        let d = await r.json();

        if (!r.ok) throw Error(d.error);

        scanDraft = d.detections;

        $("detectionRows").innerHTML = `
            <div class="detection-row">
                <b>Product name</b>
                <b>Category</b>
                <b>Qty</b>
                <b>Confidence</b>
            </div>
        ` + scanDraft.map((x, i) => detectionRow(x, i)).join("");

        $("scanReview").hidden = false;

        toast("Photo received. Please review suggestions.");

    } catch (e) {

        toast(e.message);

    } finally {

        $("dropZone").querySelector("h3").textContent =
            "Drop your household photo here";
    }
}


function detectionRow(x, i) {

    return `
        <div class="detection-row">

            <input value="${esc(x.name)}" id="detName${i}">

            <select id="detCat${i}">
                ${CATS.map(c => `
                    <option ${c === x.category ? "selected" : ""}>
                        ${esc(c)}
                    </option>
                `).join("")}
            </select>

            <input type="number"
                min="0"
                step=".1"
                value="${x.quantity}"
                id="detQty${i}">

            <span style="font-size:10px;color:#8d988f;align-self:center">
                ${x.confidence
                    ? Math.round(x.confidence * 100) + "%"
                    : "Manual review"}
            </span>

        </div>
    `;
}


async function confirmScan() {

    let rows = scanDraft.map((x, i) => ({
        name: $("detName" + i).value,
        category: $("detCat" + i).value,
        quantity: $("detQty" + i).value
    }));

    try {

        let d = await api("/api/scanner/confirm", {
            method: "POST",
            body: JSON.stringify({ items: rows })
        });

        toast(d.message);

        $("scanReview").hidden = true;
        $("scanPreview").hidden = true;

        scanDraft = [];

        await loadInventory();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


// ===============================
// RECIPES
// ===============================

async function loadRecipes() {

    try {

        let a = await api("/api/recipes");

        let em = ["🥘", "🍲", "🥗", "🍳", "🍌", "🍛"];

        $("recipeGrid").innerHTML = a.map((r, i) => `
            <article class="recipe-card">

                <div class="recipe-art">
                    ${em[i % em.length]}
                </div>

                <div class="recipe-content">

                    <h3>${esc(r.name)}</h3>

                    <p>
                        ${esc(r.cuisine)} · ${r.minutes} min ·
                        ${r.ingredients_list.length} ingredients
                    </p>

                    <span class="match">
                        ${r.match}% ingredient match
                    </span>

                    <p>
                        <b>Have:</b>
                        ${esc(r.available.join(", ") || "No matching ingredients")}
                    </p>

                    <p>
                        <b>Still need:</b>
                        ${esc(r.missing.join(", ") || "You have the listed ingredients")}
                    </p>

                    <button class="text-btn"
                        onclick="recipeDetails(${r.id})">
                        View preparation →
                    </button>

                </div>
            </article>
        `).join("") || `<div class="empty">No recipes available.</div>`;

    } catch (e) {
        toast(e.message);
    }
}


async function recipeDetails(id) {

    let a = await api("/api/recipes");

    let r = a.find(x => x.id === id);

    if (r) {
        alert(
            `${r.name}\n\n` +
            `Ingredients: ${r.ingredients}\n\n` +
            `Preparation: ${r.steps}\n\n` +
            `Check all ingredients and food-safety guidance before cooking.`
        );
    }
}


// ===============================
// SHOPPING LIST
// ===============================

async function loadShopping() {

    try {

        let a = await api("/api/shopping");

        $("shoppingList").innerHTML = a.length
            ? a.map(x => `
                <div class="shop-row ${x.done ? "done" : ""}">

                    <input type="checkbox"
                        ${x.done ? "checked" : ""}
                        onchange="toggleShop(${x.id},this.checked)">

                    <div>
                        <div class="shop-name">${esc(x.name)}</div>

                        <small>
                            ${esc(x.reason)} · ${x.quantity} ${esc(x.unit)}
                        </small>
                    </div>

                    <button class="mini-btn"
                        onclick="removeShop(${x.id})">
                        Remove
                    </button>

                </div>
            `).join("")
            : `<div class="empty">
                Your shopping list is clear. Add something you need
                or generate low-stock suggestions.
               </div>`;

    } catch (e) {
        toast(e.message);
    }
}


async function addShoppingPrompt() {

    let name = prompt(
        "What would you like to add to your shopping list?"
    );

    if (!name) return;

    try {

        await api("/api/shopping", {
            method: "POST",
            body: JSON.stringify({ name })
        });

        loadShopping();
        loadOverview();

        toast("Added to shopping list");

    } catch (e) {
        toast(e.message);
    }
}


async function generateShopping() {

    try {

        let d = await api("/api/shopping/generate", {
            method: "POST",
            body: "{}"
        });

        toast(d.message);

        loadShopping();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


async function toggleShop(id, done) {

    try {

        await api("/api/shopping/" + id, {
            method: "PUT",
            body: JSON.stringify({ done })
        });

        loadShopping();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


async function removeShop(id) {

    try {

        await api("/api/shopping/" + id, {
            method: "DELETE"
        });

        loadShopping();
        loadOverview();

    } catch (e) {
        toast(e.message);
    }
}


// ===============================
// CHEF MUMMY CHATBOT
// ===============================

async function sendChef(text) {

    let input = $("chefInput");

    let msg = text || input.value.trim();

    if (!msg) return;

    input.value = "";

    addBubble(msg, "user");

    try {

        let d = await api("/api/chef-mummy", {
            method: "POST",
            body: JSON.stringify({ message: msg })
        });

        addBubble(d.reply, "bot");

    } catch (e) {

        addBubble(e.message, "bot");
    }
}


function addBubble(msg, who) {

    let el = document.createElement("div");

    el.className = "chat-bubble " + who;
    el.textContent = msg;

    $("chatMessages").appendChild(el);

    $("chatMessages").scrollTop =
        $("chatMessages").scrollHeight;
}


// ===============================
// ANALYTICS
// ===============================

async function loadAnalytics() {

    try {

        let d = await api("/api/analytics");

        $("anTotal").textContent = d.total;
        $("anLow").textContent = d.low_stock;

        $("anValue").textContent =
            "₹" + d.recorded_value.toFixed(2);

        $("anConsumed").textContent = d.consumed_units;

        $("analyticsBars").innerHTML =
            Object.entries(d.categories).map(([k, v]) => `
                <div class="bar-row">

                    <span>${esc(k)}</span>

                    <div class="bar-track">
                        <div class="bar-fill"
                            style="width:${
                                d.total
                                    ? Math.min(
                                        100,
                                        v / Math.max(
                                            1,
                                            ...Object.values(d.categories)
                                        ) * 100
                                    )
                                    : 0
                            }%">
                        </div>
                    </div>

                    <b>${v}</b>

                </div>
            `).join("") +
            `<div class="notice">${esc(d.prediction_note)}</div>`;

    } catch (e) {
        toast(e.message);
    }
}

// =============================================
// PROFILE PAGE
// =============================================

// Load profile information independently of photo upload
async function loadProfile() {

    const fullName = $("profileFullName");
    const email = $("profileEmail");
    const memberSince = $("profileDate");

    const totalItems = $("profileTotalItems");
    const totalQuantity = $("profileTotalQuantity");
    const categories = $("profileCategories");

    const photo = $("profilePhoto");
    const initial = $("profileInitial");
    const removePhotoBtn = $("removeProfilePhoto");

    try {

        // Fetch profile details directly from Flask
        const data = await api("/api/profile", {
            cache: "no-store"
        });

        // ---------------------------------
        // PERSONAL INFORMATION
        // ---------------------------------

        if ($("profileName")) {
            $("profileName").textContent =
                data.name || "Home member";
        }

        if (fullName) {
            fullName.textContent =
                data.name || "Not available";
        }

        if (email) {
            email.textContent =
                data.email || "Not available";
        }

        // Registration date
        if (memberSince) {

            if (data.created_at) {

                const parsedDate = new Date(
                    String(data.created_at).replace(" ", "T")
                );

                memberSince.textContent =
                    Number.isNaN(parsedDate.getTime())
                        ? data.created_at
                        : parsedDate.toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "long",
                            year: "numeric"
                        });

            } else {
                memberSince.textContent = "Not available";
            }
        }

        // ---------------------------------
        // HOUSEHOLD STATISTICS
        // ---------------------------------

        if (totalItems) {
            totalItems.textContent =
                Number(data.total_items || 0).toLocaleString("en-IN");
        }

        if (totalQuantity) {
            totalQuantity.textContent =
                Number(data.total_quantity || 0).toLocaleString("en-IN", {
                    maximumFractionDigits: 2
                });
        }

        if (categories) {
            categories.textContent =
                Number(data.categories_used || 0).toLocaleString("en-IN");
        }

        // ---------------------------------
        // DEFAULT PROFILE INITIAL
        // ---------------------------------

        if (initial) {
            initial.textContent =
                (data.name || "U").trim().charAt(0).toUpperCase();

            initial.hidden = false;
        }

        // ---------------------------------
        // OPTIONAL PROFILE PHOTO
        // ---------------------------------

        if (photo) {

            // Hide old image while checking current photo
            photo.hidden = true;

            if (data.profile_photo_url) {

                photo.onload = () => {
                    photo.hidden = false;

                    if (initial) {
                        initial.hidden = true;
                    }
                };

                photo.onerror = () => {
                    photo.hidden = true;

                    if (initial) {
                        initial.hidden = false;
                    }
                };

                photo.src =
                    data.profile_photo_url +
                    (data.profile_photo_url.includes("?") ? "&" : "?") +
                    "v=" + Date.now();

            } else {

                photo.removeAttribute("src");
                photo.hidden = true;

                if (initial) {
                    initial.hidden = false;
                }
            }
        }

        // Show remove button only if a photo exists
        if (removePhotoBtn) {
            removePhotoBtn.hidden = !data.profile_photo_url;
        }

    } catch (error) {

        console.error("Profile loading error:", error);

        if (fullName) fullName.textContent = "Unable to load";
        if (email) email.textContent = "Unable to load";
        if (memberSince) memberSince.textContent = "Unable to load";

        toast("Could not load profile: " + error.message);
    }
}


// =============================================
// AUTOMATIC PROFILE DATA FETCHING
// =============================================

// Load profile whenever the Profile navigation button is clicked.
// This works even if the user has never uploaded a photo.

document.addEventListener("click", function(event) {

    const profileButton = event.target.closest('[data-page="profile"]');

    if (profileButton) {
        requestAnimationFrame(() => {
            loadProfile();
        });
    }

});

// Also load profile if it is already the active page on startup.
document.addEventListener("DOMContentLoaded", function() {

    const profilePage = $("profile");

    if (profilePage && profilePage.classList.contains("active")) {
        loadProfile();
    }

});


// =============================================
// PROFILE PHOTO UPLOAD
// =============================================

const profilePhotoInput = $("photoInput");

if (profilePhotoInput) {

    profilePhotoInput.addEventListener("change", async function() {

        const file = this.files && this.files[0];

        if (!file) return;

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        if (!allowedTypes.includes(file.type)) {

            toast("Please select a JPG, PNG or WEBP image.");
            this.value = "";
            return;
        }

        const formData = new FormData();
        formData.append("photo", file);

        try {

            const response = await fetch("/api/profile/photo", {
                method: "POST",
                body: formData,
                credentials: "same-origin"
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.error || "Photo upload failed."
                );
            }

            toast("Profile photo updated successfully!");

            // Refresh all profile details
            await loadProfile();

        } catch (error) {

            console.error("Photo upload error:", error);
            toast(error.message);

        } finally {

            this.value = "";
        }
    });
}


// =============================================
// REMOVE PROFILE PHOTO
// =============================================

const removePhotoBtn = $("removeProfilePhoto");

if (removePhotoBtn) {

    removePhotoBtn.addEventListener("click", async function() {

        if (!confirm("Are you sure you want to remove your profile picture?")) {
            return;
        }

        try {

            const response = await fetch("/api/profile/photo", {
                method: "DELETE",
                credentials: "same-origin"
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.error || "Could not remove profile picture."
                );
            }

            toast("Profile picture removed successfully!");

            // Refresh profile and show default initial
            await loadProfile();

        } catch (error) {

            console.error("Photo removal error:", error);
            toast(error.message);

        }
    });
}


// ==========================================
// DARK / LIGHT THEME TOGGLE
// ==========================================

const themeToggle = document.getElementById("themeToggle");

// Apply saved theme when the page loads
function applyTheme(theme) {

    document.documentElement.setAttribute(
        "data-theme",
        theme
    );

    if (themeToggle) {

        if (theme === "dark") {
            themeToggle.textContent = "☀️";
            themeToggle.title = "Switch to Light Mode";
        } else {
            themeToggle.textContent = "🌙";
            themeToggle.title = "Switch to Dark Mode";
        }
    }
}

// Load saved preference
const savedTheme = localStorage.getItem("homestock-theme") || "light";

applyTheme(savedTheme);

// Toggle theme on button click
if (themeToggle) {

    themeToggle.addEventListener("click", function () {

        const currentTheme =
            document.documentElement.getAttribute("data-theme") || "light";

        const newTheme =
            currentTheme === "light" ? "dark" : "light";

        // Apply new theme
        applyTheme(newTheme);

        // Save user preference
        localStorage.setItem("homestock-theme", newTheme);

    });
}



// ===============================
// INITIAL PAGE LOAD
// ===============================

loadOverview();
loadInventory();
