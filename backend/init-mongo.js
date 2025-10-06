// MongoDB Initialization Script
// This runs automatically when MongoDB container starts

print('========================================');
print('Initializing People Counting Database');
print('========================================');

// Switch to database
db = db.getSiblingDB('people_counting_db');

// Create collections with validation
print('Creating collections...');

db.createCollection('detections', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['track_id', 'timestamp', 'bbox', 'in_polygon'],
      properties: {
        track_id: { bsonType: 'int' },
        timestamp: { bsonType: 'date' },
        bbox: { bsonType: 'array' },
        in_polygon: { bsonType: 'bool' },
        area_name: { bsonType: 'string' },
        confidence: { bsonType: 'double' }
      }
    }
  }
});

db.createCollection('counting_events', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['track_id', 'event_type', 'timestamp'],
      properties: {
        track_id: { bsonType: 'int' },
        event_type: { bsonType: 'string', enum: ['entry', 'exit'] },
        timestamp: { bsonType: 'date' },
        area_name: { bsonType: 'string' }
      }
    }
  }
});

db.createCollection('polygon_config', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['area_name', 'coordinates'],
      properties: {
        area_name: { bsonType: 'string' },
        coordinates: { bsonType: 'array' },
        description: { bsonType: 'string' },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

print('✓ Collections created');

// Create indexes
print('Creating indexes...');

db.detections.createIndex({ timestamp: -1 });
db.detections.createIndex({ track_id: 1 });
db.detections.createIndex({ area_name: 1, timestamp: -1 });

db.counting_events.createIndex({ timestamp: -1 });
db.counting_events.createIndex({ track_id: 1 });
db.counting_events.createIndex({ event_type: 1, timestamp: -1 });
db.counting_events.createIndex({ area_name: 1, timestamp: -1 });

db.polygon_config.createIndex({ area_name: 1 }, { unique: true });

print('✓ Indexes created');

// Insert default polygon
print('Inserting default polygon...');

db.polygon_config.insertOne({
  area_name: 'high_risk_area_1',
  coordinates: [[300, 200], [900, 200], [900, 500], [300, 500]],
  description: 'Default high risk monitoring area',
  created_at: new Date(),
  updated_at: new Date()
});

print('✓ Default polygon inserted');

// Verify
print('Verifying setup...');
print('Collections:', db.getCollectionNames());
print('Polygon count:', db.polygon_config.count());

print('========================================');
print('Database initialization complete!');
print('========================================');