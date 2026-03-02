from model.cnn_model import create_kws_model
from data.extract_data import fetch_speech_data_in_mfcc

import tensorflow as tf

def train_kws_model(train_ds, test_ds, num_classes=7, epochs=10, lr=1e-3):
    #Get input shape and number of classes from the dataset
    for mfcc, label in train_ds.take(1):
        input_shape = mfcc.shape[1:] #Exclude batch dimension
        num_classes = len(tf.unique(label)[0])
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
        tf.keras.callbacks.EarlyStopping(monitor='val_acc', 
                                         patience=3, 
                                         restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_acc',
                                             factor=0.5,
                                             patience=2,
                                             min_lr=1e-5,
                                             verbose=1)
    ]
    
    history = model.fit(
        train_ds,
        validation_data=test_ds,
        epochs=epochs,
        callbacks=callbacks
    )

    return model, history

def test_kws_model(model, test_ds):
    results = model.evaluate(test_ds, return_dict=True)
    return results

if __name__ == "__main__":
    train_ds, test_ds = fetch_speech_data_in_mfcc()
    model, history = train_kws_model(train_ds, test_ds)
    model.save("cnn_kws_model")
    test_results = test_kws_model(model, test_ds)
    print("Test results:", test_results)