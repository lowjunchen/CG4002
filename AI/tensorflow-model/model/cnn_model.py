import tensorflow as tf

def create_kws_model(input_shape, num_classes):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=input_shape),

        tf.keras.layers.Conv2D(16, (3,3), strides=(1,1), padding='same'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.ReLU(),
        tf.keras.layers.MaxPooling2D((2,2)),

        tf.keras.layers.Conv2D(32, (3,3), padding='same'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.ReLU(),
        tf.keras.layers.MaxPooling2D((2,2)),

        tf.keras.layers.Conv2D(32, (3,3), padding='same'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.ReLU(),

        tf.keras.layers.GlobalAveragePooling2D(), #GlobalAveragePolling2D() replacing Flatten() to reduce parameters
        tf.keras.layers.Dropout(0.15),

        tf.keras.layers.Dense(num_classes)
    ])

    return model