DROP DATABASE IF EXISTS store_142;
CREATE DATABASE store_142;
USE store_142;

CREATE TABLE vendors (
    vendor_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    min_order_qty INT DEFAULT 1,
    lead_time_hours INT DEFAULT 24,
    payment_terms VARCHAR(50) DEFAULT 'NET30',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE inventory (
    sku VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    aisle INT NOT NULL,
    row_num INT NOT NULL,
    shelf_qty INT DEFAULT 0,
    backroom_qty INT DEFAULT 0,
    reorder_threshold INT DEFAULT 10,
    max_shelf_capacity INT DEFAULT 30,
    vendor_id INT,
    unit_cost DECIMAL(8,2) DEFAULT 0.00,
    last_restocked_at TIMESTAMP NULL,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

CREATE TABLE cameras (
    camera_id VARCHAR(20) PRIMARY KEY,
    aisle INT NOT NULL,
    row_start INT NOT NULL,
    row_end INT NOT NULL,
    zone VARCHAR(50) NOT NULL,
    fridge_monitored BOOLEAN DEFAULT FALSE,
    fridge_side VARCHAR(10) DEFAULT NULL,
    status ENUM('active','offline','maintenance') DEFAULT 'active',
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE camera_product_map (
    id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL,
    product_sku VARCHAR(50) NOT NULL,
    position ENUM(
        'top-left','top-middle','top-right',
        'middle-left','middle-middle','middle-right',
        'bottom-left','bottom-middle','bottom-right'
    ) NOT NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    FOREIGN KEY (product_sku) REFERENCES inventory(sku),
    UNIQUE KEY uq_cam_pos (camera_id, position),
    UNIQUE KEY uq_cam_prod (camera_id, product_sku)
);

CREATE TABLE workers (
    id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    zone VARCHAR(50) NOT NULL,
    role ENUM('stocker','cleaner','supervisor','general') DEFAULT 'general',
    status ENUM('available','busy','break','off_shift') DEFAULT 'available',
    current_ticket_id VARCHAR(20) DEFAULT NULL,
    radio_channel INT DEFAULT 1,
    shift_start TIME,
    shift_end TIME
);

CREATE TABLE managers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    auto_approve_below DECIMAL(10,2) DEFAULT 100.00,
    notify_on VARCHAR(100) DEFAULT 'vendor_order,critical,sla_breach'
);

CREATE TABLE tickets (
    ticket_id VARCHAR(20) PRIMARY KEY,
    type ENUM('restock','vendor_order','fridge','alignment','cleaning','escalation') NOT NULL,
    priority ENUM('CRITICAL','HIGH','MEDIUM','LOW') NOT NULL,
    status ENUM('open','assigned','in_progress','resolved','ordered','escalated') DEFAULT 'open',
    source_camera VARCHAR(20),
    assignee_worker_id VARCHAR(10),
    product_sku VARCHAR(50),
    location VARCHAR(100),
    sla_minutes INT DEFAULT 30,
    vendor_order_id INT DEFAULT NULL,
    manager_approved BOOLEAN DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (source_camera) REFERENCES cameras(camera_id),
    FOREIGN KEY (assignee_worker_id) REFERENCES workers(id),
    FOREIGN KEY (product_sku) REFERENCES inventory(sku)
);

CREATE TABLE vendor_orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id VARCHAR(20),
    vendor_id INT,
    product_sku VARCHAR(50),
    quantity INT,
    estimated_cost DECIMAL(10,2),
    status ENUM('pending_approval','approved','calling','confirmed','denied','delivered') DEFAULT 'pending_approval',
    manager_approved_at TIMESTAMP NULL,
    call_placed_at TIMESTAMP NULL,
    confirmed_at TIMESTAMP NULL,
    delivery_eta TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id),
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (product_sku) REFERENCES inventory(sku)
);

CREATE TABLE vision_events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    camera_id VARCHAR(20) NOT NULL,
    event_type ENUM('stockout','low_stock','misalignment','fridge_open','fridge_closed','hygiene','unknown') NOT NULL,
    position ENUM(
        'top-left','top-middle','top-right',
        'middle-left','middle-middle','middle-right',
        'bottom-left','bottom-middle','bottom-right'
    ) DEFAULT NULL,
    position_hint VARCHAR(100) DEFAULT NULL,
    raw_description TEXT,
    confidence FLOAT,
    processed BOOLEAN DEFAULT FALSE,
    matched_sku VARCHAR(50) DEFAULT NULL,
    ticket_id VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    FOREIGN KEY (matched_sku) REFERENCES inventory(sku),
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);

CREATE TABLE agent_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT,
    ticket_id VARCHAR(20),
    step_number INT,
    tool_called VARCHAR(50),
    tool_arguments JSON,
    tool_result JSON,
    model_raw_output TEXT,
    latency_ms FLOAT,
    was_correct BOOLEAN DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES vision_events(event_id)
);

-- SEED: Vendors
INSERT INTO vendors (vendor_id, name, phone, email, min_order_qty, lead_time_hours) VALUES
(1, 'Barilla Direct',  '+18009227455', 'orders@barilla.com',     20, 24),
(2, 'DairyFresh Co',   '+18005550199', 'supply@dairyfresh.com',  10, 12),
(3, 'Wonder Bakery',   '+18005550342', 'orders@wonderbread.com', 15, 18),
(4, 'Frito-Lay Dist.', '+18005550777', 'retail@fritolay.com',    25, 24),
(5, 'Chobani Supply',  '+18005550488', 'orders@chobani.com',     12, 12),
(6, 'General Mills',   '+18005550621', 'supply@genmills.com',    20, 36);

-- SEED: Inventory
INSERT INTO inventory (sku, name, category, aisle, row_num, shelf_qty, backroom_qty, reorder_threshold, max_shelf_capacity, vendor_id, unit_cost) VALUES
('pasta-barilla',     'Barilla Pasta',     'Pasta',   3, 2, 0,  24, 5,  30, 1, 1.89),
('pasta-penne',       'Barilla Penne',     'Pasta',   3, 2, 15, 20, 5,  30, 1, 2.09),
('sauce-ragu',        'Ragu Tomato Sauce', 'Pasta',   3, 1, 8,  10, 6,  25, 1, 2.49),
('milk-whole',        'Whole Milk 1gal',   'Dairy',   1, 1, 2,  0,  10, 20, 2, 3.49),
('milk-2pct',         'Milk 2% 1gal',      'Dairy',   1, 1, 5,  8,  10, 20, 2, 3.29),
('butter-unsalted',   'Unsalted Butter',   'Dairy',   1, 2, 6,  15, 8,  18, 2, 4.99),
('bread-wonder',      'Wonder Bread',      'Bakery',  2, 3, 1,  12, 8,  25, 3, 2.99),
('bread-wheat',       'Wheat Bread',       'Bakery',  2, 3, 4,  10, 8,  25, 3, 3.49),
('muffins-blueberry', 'Blueberry Muffins', 'Bakery',  2, 2, 3,  6,  4,  12, 3, 4.99),
('chips-lays',        'Lays Classic',      'Snacks',  4, 1, 0,  0,  15, 40, 4, 4.29),
('chips-doritos',     'Doritos Nacho',     'Snacks',  4, 1, 7,  12, 15, 40, 4, 4.49),
('pretzels-snyder',   'Snyders Pretzels',  'Snacks',  4, 2, 10, 8,  10, 30, 4, 3.99),
('yogurt-greek',      'Greek Yogurt',      'Dairy',   1, 3, 4,  36, 12, 24, 5, 5.99),
('yogurt-vanilla',    'Vanilla Yogurt',    'Dairy',   1, 3, 6,  20, 12, 24, 5, 5.49),
('cereal-cheerios',   'Cheerios',          'Cereal',  5, 2, 3,  8,  6,  20, 6, 4.49),
('cereal-granola',    'Granola Crunch',    'Cereal',  5, 2, 5,  4,  6,  20, 6, 5.29);

-- SEED: Cameras
INSERT INTO cameras (camera_id, aisle, row_start, row_end, zone, fridge_monitored, fridge_side) VALUES
('CAM-01', 1, 1, 3, 'Dairy',        TRUE,  'left'),
('CAM-02', 2, 1, 4, 'Bakery',       FALSE, NULL),
('CAM-03', 3, 1, 3, 'Pasta/Sauce',  FALSE, NULL),
('CAM-04', 4, 1, 2, 'Snacks',       FALSE, NULL),
('CAM-05', 5, 1, 3, 'Cereal',       FALSE, NULL),
('CAM-06', 1, 1, 3, 'Dairy-Fridge', TRUE,  'right');

-- SEED: Camera-Product Map (3x3 grid)
INSERT INTO camera_product_map (camera_id, product_sku, position) VALUES
('CAM-01', 'milk-whole',       'top-left'),
('CAM-01', 'milk-2pct',        'top-right'),
('CAM-01', 'butter-unsalted',  'middle-middle'),
('CAM-01', 'yogurt-greek',     'bottom-left'),
('CAM-01', 'yogurt-vanilla',   'bottom-right'),
('CAM-02', 'muffins-blueberry','top-middle'),
('CAM-02', 'bread-wonder',     'middle-left'),
('CAM-02', 'bread-wheat',      'middle-right'),
('CAM-03', 'pasta-barilla',    'top-left'),
('CAM-03', 'pasta-penne',      'top-right'),
('CAM-03', 'sauce-ragu',       'middle-middle'),
('CAM-04', 'chips-lays',       'top-left'),
('CAM-04', 'chips-doritos',    'top-right'),
('CAM-04', 'pretzels-snyder',  'bottom-middle'),
('CAM-05', 'cereal-cheerios',  'middle-left'),
('CAM-05', 'cereal-granola',   'middle-right'),
('CAM-06', 'milk-whole',       'top-left'),
('CAM-06', 'milk-2pct',        'top-right'),
('CAM-06', 'yogurt-greek',     'bottom-left'),
('CAM-06', 'yogurt-vanilla',   'bottom-right');

-- SEED: Workers
INSERT INTO workers (id, name, zone, role, status, radio_channel, shift_start, shift_end) VALUES
('W1', 'Marcus', 'Aisles 1-2', 'stocker',    'available', 1, '06:00', '14:00'),
('W2', 'Priya',  'Aisles 3-4', 'stocker',    'available', 1, '06:00', '14:00'),
('W3', 'James',  'Aisles 5-6', 'stocker',    'available', 2, '10:00', '18:00'),
('W4', 'Sofia',  'Cleaning',   'cleaner',    'available', 2, '06:00', '14:00'),
('W5', 'Alex',   'All',        'supervisor', 'available', 1, '06:00', '18:00');

-- SEED: Manager
INSERT INTO managers (name, phone, email, auto_approve_below) VALUES
('Rachel Kim', '+15559876543', 'rachel.kim@store142.com', 150.00);

-- ════════════════════════════════════════════════════════════════
-- APPEND THIS TO THE END OF init.sql
-- Pre-existing agent decisions = training data for finetune-db
-- ════════════════════════════════════════════════════════════════

-- ── Past Tickets (resolved) ────────────────────────────────────

INSERT INTO tickets (ticket_id, type, priority, status, source_camera, assignee_worker_id, product_sku, location, sla_minutes, manager_approved, created_at, assigned_at, resolved_at) VALUES
('TKT-H001', 'restock',      'HIGH',     'resolved', 'CAM-03', 'W2', 'pasta-barilla',   'Aisle 3, Row 2', 15,   NULL,  '2025-02-27 08:12:00', '2025-02-27 08:12:05', '2025-02-27 08:20:00'),
('TKT-H002', 'vendor_order', 'HIGH',     'resolved', 'CAM-04', NULL,  'chips-lays',      'Aisle 4, Row 1', 240,  TRUE,  '2025-02-27 09:30:00', NULL,                   '2025-02-27 13:30:00'),
('TKT-H003', 'fridge',       'CRITICAL', 'resolved', 'CAM-01', 'W1', NULL,               'Aisle 1, Dairy fridge, left side', 2, NULL, '2025-02-27 10:05:00', '2025-02-27 10:05:03', '2025-02-27 10:06:30'),
('TKT-H004', 'alignment',    'LOW',      'resolved', 'CAM-05', 'W3', 'cereal-cheerios',  'Aisle 5, Row 2', 30,   NULL,  '2025-02-27 11:00:00', '2025-02-27 11:00:08', '2025-02-27 11:15:00'),
('TKT-H005', 'cleaning',     'MEDIUM',   'resolved', 'CAM-02', 'W4', NULL,               'Aisle 2, Bakery zone', 10, NULL, '2025-02-27 11:45:00', '2025-02-27 11:45:06', '2025-02-27 11:52:00'),
('TKT-H006', 'restock',      'HIGH',     'resolved', 'CAM-01', 'W1', 'milk-whole',       'Aisle 1, Row 1', 15,   NULL,  '2025-02-27 13:00:00', '2025-02-27 13:00:04', '2025-02-27 13:10:00'),
('TKT-H007', 'vendor_order', 'HIGH',     'resolved', 'CAM-01', NULL,  'milk-whole',       'Aisle 1, Row 1', 240,  TRUE,  '2025-02-27 14:20:00', NULL,                   '2025-02-27 18:00:00'),
('TKT-H008', 'fridge',       'CRITICAL', 'resolved', 'CAM-06', 'W1', NULL,               'Aisle 1, Dairy fridge, right side', 2, NULL, '2025-02-27 15:10:00', '2025-02-27 15:10:02', '2025-02-27 15:11:20'),
('TKT-H009', 'restock',      'HIGH',     'resolved', 'CAM-02', 'W2', 'bread-wonder',     'Aisle 2, Row 3', 15,   NULL,  '2025-02-27 16:00:00', '2025-02-27 16:00:06', '2025-02-27 16:12:00'),
('TKT-H010', 'cleaning',     'MEDIUM',   'resolved', 'CAM-01', 'W4', NULL,               'Aisle 1, Dairy zone', 10, NULL, '2025-02-27 16:30:00', '2025-02-27 16:30:05', '2025-02-27 16:38:00'),
('TKT-H011', 'alignment',    'LOW',      'resolved', 'CAM-04', 'W2', 'chips-doritos',    'Aisle 4, Row 1', 30,   NULL,  '2025-02-28 07:15:00', '2025-02-28 07:15:07', '2025-02-28 07:30:00'),
('TKT-H012', 'vendor_order', 'HIGH',     'resolved', 'CAM-01', NULL,  'butter-unsalted',  'Aisle 1, Row 2', 240,  TRUE,  '2025-02-28 08:00:00', NULL,                   '2025-02-28 12:00:00');

-- ── Past Vendor Orders ─────────────────────────────────────────

INSERT INTO vendor_orders (ticket_id, vendor_id, product_sku, quantity, estimated_cost, status, manager_approved_at, call_placed_at, confirmed_at, created_at) VALUES
('TKT-H002', 4, 'chips-lays',      45, 193.05, 'confirmed', '2025-02-27 09:35:00', '2025-02-27 09:36:00', '2025-02-27 09:38:00', '2025-02-27 09:30:00'),
('TKT-H007', 2, 'milk-whole',      30, 104.70, 'confirmed', '2025-02-27 14:25:00', '2025-02-27 14:26:00', '2025-02-27 14:28:00', '2025-02-27 14:20:00'),
('TKT-H012', 2, 'butter-unsalted', 24, 119.76, 'confirmed', '2025-02-28 08:05:00', '2025-02-28 08:06:00', '2025-02-28 08:08:00', '2025-02-28 08:00:00');

-- ── Past Vision Events (processed) ────────────────────────────

INSERT INTO vision_events (event_id, camera_id, event_type, position, position_hint, confidence, processed, matched_sku, ticket_id, created_at) VALUES
(101, 'CAM-03', 'stockout',     'top-left',     NULL,                        0.94, TRUE, 'pasta-barilla',   'TKT-H001', '2025-02-27 08:12:00'),
(102, 'CAM-04', 'stockout',     'top-left',     NULL,                        0.96, TRUE, 'chips-lays',      'TKT-H002', '2025-02-27 09:30:00'),
(103, 'CAM-01', 'fridge_open',  NULL,           NULL,                        0.98, TRUE, NULL,              'TKT-H003', '2025-02-27 10:05:00'),
(104, 'CAM-05', 'misalignment', 'middle-left',  NULL,                        0.85, TRUE, 'cereal-cheerios', 'TKT-H004', '2025-02-27 11:00:00'),
(105, 'CAM-02', 'hygiene',      NULL,           NULL,                        0.91, TRUE, NULL,              'TKT-H005', '2025-02-27 11:45:00'),
(106, 'CAM-01', 'stockout',     'top-left',     NULL,                        0.89, TRUE, 'milk-whole',      'TKT-H006', '2025-02-27 13:00:00'),
(107, 'CAM-01', 'stockout',     'top-left',     NULL,                        0.92, TRUE, 'milk-whole',      'TKT-H007', '2025-02-27 14:20:00'),
(108, 'CAM-06', 'fridge_open',  NULL,           NULL,                        0.97, TRUE, NULL,              'TKT-H008', '2025-02-27 15:10:00'),
(109, 'CAM-02', 'stockout',     'middle-left',  NULL,                        0.88, TRUE, 'bread-wonder',    'TKT-H009', '2025-02-27 16:00:00'),
(110, 'CAM-01', 'hygiene',      NULL,           'bottom shelf sticky residue',0.87, TRUE, NULL,              'TKT-H010', '2025-02-27 16:30:00'),
(111, 'CAM-04', 'misalignment', 'top-right',    NULL,                        0.83, TRUE, 'chips-doritos',   'TKT-H011', '2025-02-28 07:15:00'),
(112, 'CAM-01', 'stockout',     'middle-middle',NULL,                        0.90, TRUE, 'butter-unsalted', 'TKT-H012', '2025-02-28 08:00:00');

-- ── Past Agent Log (the model's decisions = training data) ─────
-- Each row = one step in the tool-calling chain
-- finetune.py --from-db reads these to create training examples

-- Event 101: Stockout pasta → backroom has stock → assign worker
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(101, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-03"}',
 '{"camera_id": "CAM-03", "aisle": 3, "zone": "Pasta/Sauce", "fridge_monitored": false, "products": [{"sku": "pasta-barilla", "name": "Barilla Pasta", "position": "top-left"}, {"sku": "pasta-penne", "name": "Barilla Penne", "position": "top-right"}, {"sku": "sauce-ragu", "name": "Ragu Tomato Sauce", "position": "middle-middle"}]}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-03"}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:00'),
(101, NULL, 2, 'resolve_product',
 '{"camera_id": "CAM-03", "position": "top-left"}',
 '{"sku": "pasta-barilla", "name": "Barilla Pasta", "aisle": 3, "row": 2, "match": "exact"}',
 '<tool_call>\n{"name": "resolve_product", "arguments": {"camera_id": "CAM-03", "position": "top-left"}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:00'),
(101, NULL, 3, 'check_stock',
 '{"product_sku": "pasta-barilla"}',
 '{"sku": "pasta-barilla", "name": "Barilla Pasta", "shelf_qty": 0, "backroom_qty": 24, "reorder_threshold": 5, "unit_cost": 1.89, "vendor_name": "Barilla Direct"}',
 '<tool_call>\n{"name": "check_stock", "arguments": {"product_sku": "pasta-barilla"}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:01'),
(101, 'TKT-H001', 4, 'create_ticket',
 '{"ticket_type": "restock", "priority": "HIGH", "source_camera": "CAM-03", "location": "Aisle 3, Row 2", "sla_minutes": 15, "product_sku": "pasta-barilla"}',
 '{"ticket_id": "TKT-H001", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "restock", "priority": "HIGH", "source_camera": "CAM-03", "location": "Aisle 3, Row 2", "sla_minutes": 15, "product_sku": "pasta-barilla"}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:01'),
(101, 'TKT-H001', 5, 'find_worker',
 '{"aisle": 3, "role": "stocker"}',
 '{"id": "W2", "name": "Priya", "zone": "Aisles 3-4", "available": true}',
 '<tool_call>\n{"name": "find_worker", "arguments": {"aisle": 3, "role": "stocker"}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:02'),
(101, 'TKT-H001', 6, 'assign_worker',
 '{"worker_id": "W2", "ticket_id": "TKT-H001", "announcement": "Priya. Aisle 3, Row 2. Barilla Pasta shelf empty. Backroom has 24 units. Please restock within 15 minutes."}',
 '{"assigned": true, "worker_id": "W2", "ticket_id": "TKT-H001"}',
 '<tool_call>\n{"name": "assign_worker", "arguments": {"worker_id": "W2", "ticket_id": "TKT-H001", "announcement": "Priya. Aisle 3, Row 2. Barilla Pasta shelf empty. Backroom has 24 units. Please restock within 15 minutes."}}\n</tool_call>',
 TRUE, '2025-02-27 08:12:02'),
(101, 'TKT-H001', 7, 'done', '{}', '{}',
 '<done>Stockout at CAM-03 top-left. Resolved: Barilla Pasta. Backroom has 24 units. Created TKT-H001 (HIGH, 15min). Assigned Priya to restock.</done>',
 TRUE, '2025-02-27 08:12:03');

-- Event 102: Stockout chips → no backroom → vendor order
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(102, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-04"}',
 '{"camera_id": "CAM-04", "aisle": 4, "zone": "Snacks", "products": [{"sku": "chips-lays", "name": "Lays Classic", "position": "top-left"}, {"sku": "chips-doritos", "name": "Doritos Nacho", "position": "top-right"}, {"sku": "pretzels-snyder", "name": "Snyders Pretzels", "position": "bottom-middle"}]}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-04"}}\n</tool_call>',
 TRUE, '2025-02-27 09:30:00'),
(102, NULL, 2, 'resolve_product',
 '{"camera_id": "CAM-04", "position": "top-left"}',
 '{"sku": "chips-lays", "name": "Lays Classic", "aisle": 4, "row": 1, "match": "exact"}',
 '<tool_call>\n{"name": "resolve_product", "arguments": {"camera_id": "CAM-04", "position": "top-left"}}\n</tool_call>',
 TRUE, '2025-02-27 09:30:00'),
(102, NULL, 3, 'check_stock',
 '{"product_sku": "chips-lays"}',
 '{"sku": "chips-lays", "shelf_qty": 0, "backroom_qty": 0, "reorder_threshold": 15, "unit_cost": 4.29, "vendor_name": "Frito-Lay Dist.", "min_order_qty": 25}',
 '<tool_call>\n{"name": "check_stock", "arguments": {"product_sku": "chips-lays"}}\n</tool_call>',
 TRUE, '2025-02-27 09:30:01'),
(102, 'TKT-H002', 4, 'create_ticket',
 '{"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-04", "location": "Aisle 4, Row 1", "sla_minutes": 240, "product_sku": "chips-lays"}',
 '{"ticket_id": "TKT-H002", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-04", "location": "Aisle 4, Row 1", "sla_minutes": 240, "product_sku": "chips-lays"}}\n</tool_call>',
 TRUE, '2025-02-27 09:30:01'),
(102, 'TKT-H002', 5, 'request_vendor_order',
 '{"product_sku": "chips-lays", "ticket_id": "TKT-H002", "quantity": 45, "reason": "Shelf and backroom both empty. High-demand snack product."}',
 '{"order_created": true, "vendor": "Frito-Lay Dist.", "quantity": 45, "cost": 193.05, "auto_approved": false, "status": "pending_approval"}',
 '<tool_call>\n{"name": "request_vendor_order", "arguments": {"product_sku": "chips-lays", "ticket_id": "TKT-H002", "quantity": 45, "reason": "Shelf and backroom both empty. High-demand snack product."}}\n</tool_call>',
 TRUE, '2025-02-27 09:30:02'),
(102, 'TKT-H002', 6, 'done', '{}', '{}',
 '<done>Stockout at CAM-04. Lays Classic — both empty. Created TKT-H002. Vendor order 45 units from Frito-Lay at $193.05. Pending manager approval.</done>',
 TRUE, '2025-02-27 09:30:02');

-- Event 103: Fridge open → CRITICAL → immediate worker
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(103, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-01"}',
 '{"camera_id": "CAM-01", "aisle": 1, "zone": "Dairy", "fridge_monitored": true, "fridge_side": "left"}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}\n</tool_call>',
 TRUE, '2025-02-27 10:05:00'),
(103, 'TKT-H003', 2, 'create_ticket',
 '{"ticket_type": "fridge", "priority": "CRITICAL", "source_camera": "CAM-01", "location": "Aisle 1, Dairy fridge, left side", "sla_minutes": 2}',
 '{"ticket_id": "TKT-H003", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "fridge", "priority": "CRITICAL", "source_camera": "CAM-01", "location": "Aisle 1, Dairy fridge, left side", "sla_minutes": 2}}\n</tool_call>',
 TRUE, '2025-02-27 10:05:01'),
(103, 'TKT-H003', 3, 'find_worker',
 '{"aisle": 1, "role": "any"}',
 '{"id": "W1", "name": "Marcus", "zone": "Aisles 1-2", "available": true}',
 '<tool_call>\n{"name": "find_worker", "arguments": {"aisle": 1, "role": "any"}}\n</tool_call>',
 TRUE, '2025-02-27 10:05:01'),
(103, 'TKT-H003', 4, 'assign_worker',
 '{"worker_id": "W1", "ticket_id": "TKT-H003", "announcement": "URGENT. Marcus. Aisle 1, dairy fridge left side is open. Close immediately. Product temperature at risk. You have 2 minutes."}',
 '{"assigned": true, "worker_id": "W1", "ticket_id": "TKT-H003"}',
 '<tool_call>\n{"name": "assign_worker", "arguments": {"worker_id": "W1", "ticket_id": "TKT-H003", "announcement": "URGENT. Marcus. Aisle 1, dairy fridge left side is open. Close immediately. Product temperature at risk. You have 2 minutes."}}\n</tool_call>',
 TRUE, '2025-02-27 10:05:02'),
(103, 'TKT-H003', 5, 'done', '{}', '{}',
 '<done>Fridge open at CAM-01. Left side dairy fridge. CRITICAL, 2min SLA. Created TKT-H003. Assigned Marcus immediately.</done>',
 TRUE, '2025-02-27 10:05:02');

-- Event 104: Misalignment cereal
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(104, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-05"}',
 '{"camera_id": "CAM-05", "aisle": 5, "zone": "Cereal", "products": [{"sku": "cereal-cheerios", "name": "Cheerios", "position": "middle-left"}, {"sku": "cereal-granola", "name": "Granola Crunch", "position": "middle-right"}]}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-05"}}\n</tool_call>',
 TRUE, '2025-02-27 11:00:00'),
(104, NULL, 2, 'resolve_product',
 '{"camera_id": "CAM-05", "position": "middle-left"}',
 '{"sku": "cereal-cheerios", "name": "Cheerios", "aisle": 5, "row": 2, "match": "exact"}',
 '<tool_call>\n{"name": "resolve_product", "arguments": {"camera_id": "CAM-05", "position": "middle-left"}}\n</tool_call>',
 TRUE, '2025-02-27 11:00:01'),
(104, 'TKT-H004', 3, 'create_ticket',
 '{"ticket_type": "alignment", "priority": "LOW", "source_camera": "CAM-05", "location": "Aisle 5, Row 2", "sla_minutes": 30, "product_sku": "cereal-cheerios"}',
 '{"ticket_id": "TKT-H004", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "alignment", "priority": "LOW", "source_camera": "CAM-05", "location": "Aisle 5, Row 2", "sla_minutes": 30, "product_sku": "cereal-cheerios"}}\n</tool_call>',
 TRUE, '2025-02-27 11:00:01'),
(104, 'TKT-H004', 4, 'find_worker',
 '{"aisle": 5, "role": "stocker"}',
 '{"id": "W3", "name": "James", "zone": "Aisles 5-6", "available": true}',
 '<tool_call>\n{"name": "find_worker", "arguments": {"aisle": 5, "role": "stocker"}}\n</tool_call>',
 TRUE, '2025-02-27 11:00:02'),
(104, 'TKT-H004', 5, 'assign_worker',
 '{"worker_id": "W3", "ticket_id": "TKT-H004", "announcement": "James. Aisle 5, Row 2. Cheerios products misaligned. Please face and straighten. You have 30 minutes."}',
 '{"assigned": true, "worker_id": "W3", "ticket_id": "TKT-H004"}',
 '<tool_call>\n{"name": "assign_worker", "arguments": {"worker_id": "W3", "ticket_id": "TKT-H004", "announcement": "James. Aisle 5, Row 2. Cheerios products misaligned. Please face and straighten. You have 30 minutes."}}\n</tool_call>',
 TRUE, '2025-02-27 11:00:02'),
(104, 'TKT-H004', 6, 'done', '{}', '{}',
 '<done>Misalignment at CAM-05 middle-left. Cheerios at Aisle 5, Row 2. Created TKT-H004 (LOW, 30min). Assigned James.</done>',
 TRUE, '2025-02-27 11:00:03');

-- Event 105: Hygiene → cleaner
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(105, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-02"}',
 '{"camera_id": "CAM-02", "aisle": 2, "zone": "Bakery", "fridge_monitored": false}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-02"}}\n</tool_call>',
 TRUE, '2025-02-27 11:45:00'),
(105, 'TKT-H005', 2, 'create_ticket',
 '{"ticket_type": "cleaning", "priority": "MEDIUM", "source_camera": "CAM-02", "location": "Aisle 2, Bakery zone", "sla_minutes": 10}',
 '{"ticket_id": "TKT-H005", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "cleaning", "priority": "MEDIUM", "source_camera": "CAM-02", "location": "Aisle 2, Bakery zone", "sla_minutes": 10}}\n</tool_call>',
 TRUE, '2025-02-27 11:45:01'),
(105, 'TKT-H005', 3, 'find_worker',
 '{"aisle": 2, "role": "cleaner"}',
 '{"id": "W4", "name": "Sofia", "zone": "Cleaning", "available": true}',
 '<tool_call>\n{"name": "find_worker", "arguments": {"aisle": 2, "role": "cleaner"}}\n</tool_call>',
 TRUE, '2025-02-27 11:45:01'),
(105, 'TKT-H005', 4, 'assign_worker',
 '{"worker_id": "W4", "ticket_id": "TKT-H005", "announcement": "Sofia. Aisle 2, Bakery zone. Hygiene issue on shelf surface. Please clean and sanitize immediately. You have 10 minutes."}',
 '{"assigned": true, "worker_id": "W4", "ticket_id": "TKT-H005"}',
 '<tool_call>\n{"name": "assign_worker", "arguments": {"worker_id": "W4", "ticket_id": "TKT-H005", "announcement": "Sofia. Aisle 2, Bakery zone. Hygiene issue on shelf surface. Please clean and sanitize immediately. You have 10 minutes."}}\n</tool_call>',
 TRUE, '2025-02-27 11:45:02'),
(105, 'TKT-H005', 5, 'done', '{}', '{}',
 '<done>Hygiene issue at CAM-02, Aisle 2 Bakery. Created TKT-H005 (MEDIUM, 10min). Assigned Sofia (cleaner).</done>',
 TRUE, '2025-02-27 11:45:02');

-- Event 110: Hygiene with fuzzy position hint
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(110, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-01"}',
 '{"camera_id": "CAM-01", "aisle": 1, "zone": "Dairy", "fridge_monitored": true, "fridge_side": "left"}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}\n</tool_call>',
 TRUE, '2025-02-27 16:30:00'),
(110, 'TKT-H010', 2, 'create_ticket',
 '{"ticket_type": "cleaning", "priority": "MEDIUM", "source_camera": "CAM-01", "location": "Aisle 1, Dairy zone", "sla_minutes": 10}',
 '{"ticket_id": "TKT-H010", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "cleaning", "priority": "MEDIUM", "source_camera": "CAM-01", "location": "Aisle 1, Dairy zone", "sla_minutes": 10}}\n</tool_call>',
 TRUE, '2025-02-27 16:30:01'),
(110, 'TKT-H010', 3, 'find_worker',
 '{"aisle": 1, "role": "cleaner"}',
 '{"id": "W4", "name": "Sofia", "zone": "Cleaning", "available": true}',
 '<tool_call>\n{"name": "find_worker", "arguments": {"aisle": 1, "role": "cleaner"}}\n</tool_call>',
 TRUE, '2025-02-27 16:30:01'),
(110, 'TKT-H010', 4, 'assign_worker',
 '{"worker_id": "W4", "ticket_id": "TKT-H010", "announcement": "Sofia. Aisle 1, Dairy zone. Sticky residue on bottom shelf. Please clean immediately. You have 10 minutes."}',
 '{"assigned": true, "worker_id": "W4", "ticket_id": "TKT-H010"}',
 '<tool_call>\n{"name": "assign_worker", "arguments": {"worker_id": "W4", "ticket_id": "TKT-H010", "announcement": "Sofia. Aisle 1, Dairy zone. Sticky residue on bottom shelf. Please clean immediately. You have 10 minutes."}}\n</tool_call>',
 TRUE, '2025-02-27 16:30:02'),
(110, 'TKT-H010', 5, 'done', '{}', '{}',
 '<done>Hygiene at CAM-01 Dairy zone. Bottom shelf sticky residue. Created TKT-H010 (MEDIUM, 10min). Assigned Sofia.</done>',
 TRUE, '2025-02-27 16:30:02');

-- Event 112: Stockout butter → no backroom → auto-approved (under $150)
INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output, was_correct, created_at) VALUES
(112, NULL, 1, 'lookup_camera',
 '{"camera_id": "CAM-01"}',
 '{"camera_id": "CAM-01", "aisle": 1, "zone": "Dairy", "products": [{"sku": "milk-whole", "position": "top-left"}, {"sku": "milk-2pct", "position": "top-right"}, {"sku": "butter-unsalted", "position": "middle-middle"}, {"sku": "yogurt-greek", "position": "bottom-left"}, {"sku": "yogurt-vanilla", "position": "bottom-right"}]}',
 '<tool_call>\n{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}\n</tool_call>',
 TRUE, '2025-02-28 08:00:00'),
(112, NULL, 2, 'resolve_product',
 '{"camera_id": "CAM-01", "position": "middle-middle"}',
 '{"sku": "butter-unsalted", "name": "Unsalted Butter", "aisle": 1, "row": 2, "match": "exact"}',
 '<tool_call>\n{"name": "resolve_product", "arguments": {"camera_id": "CAM-01", "position": "middle-middle"}}\n</tool_call>',
 TRUE, '2025-02-28 08:00:01'),
(112, NULL, 3, 'check_stock',
 '{"product_sku": "butter-unsalted"}',
 '{"sku": "butter-unsalted", "shelf_qty": 0, "backroom_qty": 0, "reorder_threshold": 8, "unit_cost": 4.99, "vendor_name": "DairyFresh Co", "min_order_qty": 10}',
 '<tool_call>\n{"name": "check_stock", "arguments": {"product_sku": "butter-unsalted"}}\n</tool_call>',
 TRUE, '2025-02-28 08:00:01'),
(112, 'TKT-H012', 4, 'create_ticket',
 '{"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-01", "location": "Aisle 1, Row 2", "sla_minutes": 240, "product_sku": "butter-unsalted"}',
 '{"ticket_id": "TKT-H012", "status": "open"}',
 '<tool_call>\n{"name": "create_ticket", "arguments": {"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-01", "location": "Aisle 1, Row 2", "sla_minutes": 240, "product_sku": "butter-unsalted"}}\n</tool_call>',
 TRUE, '2025-02-28 08:00:02'),
(112, 'TKT-H012', 5, 'request_vendor_order',
 '{"product_sku": "butter-unsalted", "ticket_id": "TKT-H012", "quantity": 24, "reason": "Shelf and backroom empty. Perishable dairy, needs fast restock."}',
 '{"order_created": true, "vendor": "DairyFresh Co", "quantity": 24, "cost": 119.76, "auto_approved": true, "status": "approved"}',
 '<tool_call>\n{"name": "request_vendor_order", "arguments": {"product_sku": "butter-unsalted", "ticket_id": "TKT-H012", "quantity": 24, "reason": "Shelf and backroom empty. Perishable dairy, needs fast restock."}}\n</tool_call>',
 TRUE, '2025-02-28 08:00:02'),
(112, 'TKT-H012', 6, 'done', '{}', '{}',
 '<done>Stockout at CAM-01. Unsalted Butter — empty everywhere. Created TKT-H012. Auto-approved 24 units from DairyFresh Co at $119.76 (under $150 threshold).</done>',
 TRUE, '2025-02-28 08:00:03');

