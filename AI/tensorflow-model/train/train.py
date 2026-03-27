from model.cnn_model import create_kws_model
from data.extract_data import load_custom_dataset

import tensorflow as tf

def train_kws_model(train_ds, num_classes=7, epochs=80, lr=1e-3):
    #Get input shape and number of classes from the dataset
    for mfcc, label in train_ds.take(1):
        input_shape = mfcc.shape[1:] #Exclude batch dimension
        print("Input shape:", input_shape)
        print("Number of classes:", num_classes)

    #Create the model
    model = create_kws_model(input_shape, num_classes)

    #Compile the model with loss and optimizer
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[
            tf.keras.metrics.SparseCategoricalAccuracy(name="acc")
        ]
    )

    model.summary()

    callbacks =[
        tf.keras.callbacks.ReduceLROnPlateau(monitor='acc',
                                             factor=0.5,
                                             patience=5,
                                             min_lr=1e-6,
                                             verbose=1),
        tf.keras.callbacks.EarlyStopping(monitor='acc',
                                         patience=8,
                                         restore_best_weights=True,
                                         verbose=1)
    ]

    train_ds = train_ds.shuffle(buffer_size=256, reshuffle_each_iteration=True)

    history = model.fit(
        train_ds,
        epochs=epochs,
        callbacks=callbacks
    )

    return model, history

if __name__ == "__main__":
    train_ds = load_custom_dataset(batch_size=32, augment=True)
    model, history = train_kws_model(train_ds)
    model.save("cnn_kws_model")
    print("Training complete. Model saved to cnn_kws_model/")