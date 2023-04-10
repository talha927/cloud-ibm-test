import tensorflow as tf
import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ["KMP_SETTINGS"] = "false"

import numpy as np
import glob
from matplotlib import pyplot as plt
% matplotlib
inline
import time
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model, Sequential
from tensorflow.keras.layers import Conv2D, BatchNormalization, LeakyReLU, Conv2DTranspose, Dropout, ReLU, Input, \
    Concatenate, concatenate
from tqdm import tqdm

import pathlib
import datetime
from IPython import display


def read_png(path):
    img = tf.io.read_file(path)
    img = tf.image.decode_png(img, channels=3)
    return img


def split_image(image):
    w = tf.shape(image)[1]
    w = w // 2
    sketch_image = image[:, :w, :]
    colored_image = image[:, w:, :]
    sketch_image = tf.image.resize(sketch_image, (256, 256))
    colored_image = tf.image.resize(colored_image, (256, 256))
    return sketch_image, colored_image


def flip_image(image):
    return tf.image.flip_left_right(image)


def random_jitter(sketch_image, colored_image):
    #     sketch_image, colored_image = resize(sketch_image, colored_image, 286, 286)

    #     sketch_image, colored_image = random_crop(sketch_image, colored_image)

    if tf.random.uniform(()) > 0.5:
        sketch_image = flip_image(sketch_image)
        colored_image = flip_image(colored_image)

    return sketch_image, colored_image


def normalize(sketch_image, colored_image):
    sketch_image = tf.cast(sketch_image, tf.float32) / 127.5 - 1
    colored_image = tf.cast(colored_image, tf.float32) / 127.5 - 1
    return sketch_image, colored_image


def load_image_train(image_path):
    image = read_png(image_path)
    sketch_image, colored_image = split_image(image)
    sketch_image, colored_image = random_jitter(sketch_image, colored_image)
    sketch_image, colored_image = normalize(sketch_image, colored_image)

    return colored_image, sketch_image


train_path = 'C:/Users/intel/Desktop/FYP/anime-sketch-colorization-pair/data/train/'
# train_path = '/content/data/train/'
train_images_path = [os.path.join(train_path, image_name) for image_name in os.listdir(train_path)]
print(len(train_images_path))

BATCH_SIZE = 4
BUFFER_SIZE = 400

train_dataset = tf.data.Dataset.from_tensor_slices(train_images_path)
train_dataset = train_dataset.map(load_image_train, num_parallel_calls=tf.data.experimental.AUTOTUNE)
train_dataset = train_dataset.shuffle(BUFFER_SIZE).batch(BATCH_SIZE)

for sketch, color in train_dataset.take(1):
    plt.subplot(1, 2, 1)
    plt.imshow(tf.keras.preprocessing.image.array_to_img(sketch[0]))
    plt.subplot(1, 2, 2)
    plt.imshow(tf.keras.preprocessing.image.array_to_img(color[0]))


def load_image_test(image_path):
    image = read_png(image_path) \
 \
            sketch_image, colored_image = split_image(image)
    sketch_image, colored_image = normalize(sketch_image, colored_image)

    return colored_image, sketch_image


test_path = 'C:/Users/intel/Desktop/FYP/anime-sketch-colorization-pair/data/train/'
test_images_path = [os.path.join(test_path, image_name) for image_name in os.listdir(test_path)]
print(len(test_images_path))

test_dataset = tf.data.Dataset.from_tensor_slices(test_images_path)
test_dataset = test_dataset.map(load_image_test)
test_dataset = test_dataset.batch(BATCH_SIZE)

for sketch, color in test_dataset.take(1):
    plt.subplot(1, 2, 1)
    plt.imshow(tf.keras.preprocessing.image.array_to_img(sketch[0]))
    plt.subplot(1, 2, 2)
    plt.imshow(tf.keras.preprocessing.image.array_to_img(color[0]))

OUTPUT_CHANNELS = 3


def downsample(filters, size, apply_batchnorm=True):
    block = Sequential()
    block.add(Conv2D(filters, size, strides=2, padding='same', use_bias=False))

    if apply_batchnorm:
        block.add(BatchNormalization())

    block.add(LeakyReLU())

    return block


def upsample(filters, size, apply_dropout=False):
    block = Sequential()
    block.add(Conv2DTranspose(filters, size, strides=2, padding='same', use_bias=False))
    block.add(BatchNormalization())

    if apply_dropout:
        block.add(Dropout(0.5))

    block.add(ReLU())

    return block


def Generator():
    inp = Input(shape=[256, 256, 3])
    x = inp

    down_stack = [
        downsample(64, 4, apply_batchnorm=False),
        downsample(128, 4),
        downsample(256, 4),
        downsample(512, 4),
        downsample(512, 4),
        downsample(512, 4),
        downsample(512, 4),
    ]

    bottleneck = downsample(512, 4)
    # decoder stack
    up_stack = [
        upsample(512, 4, apply_dropout=True),
        upsample(512, 4, apply_dropout=True),
        upsample(512, 4, apply_dropout=True),
        upsample(512, 4),
        upsample(256, 4),
        upsample(128, 4),
        upsample(64, 4),
    ]

    last_layer = Conv2DTranspose(OUTPUT_CHANNELS, 4, strides=2, padding='same', activation='tanh')

    # Downsampling
    skips = []
    for down in down_stack:
        x = down(x)
        skips.append(x)

    x = bottleneck(x)
    skips.reverse()

    # Upsampling + creating skip connections for the i-th encoder and (n-i)-th decoder
    for up, skip in zip(up_stack, skips):
        x = up(x)
        x = Concatenate()([x, skip])

    x = last_layer(x)

    return Model(inputs=inp, outputs=x)


generator = Generator()
tf.keras.utils.plot_model(generator, show_shapes=True, dpi=64)


def Discriminator():
    inp = Input(shape=[256, 256, 3], name='sketch_image')
    target = Input(shape=[256, 256, 3], name='colored_image')

    x = concatenate([inp, target])

    block_stack = [
        downsample(64, 4, apply_batchnorm=False),
        downsample(128, 4),
        downsample(256, 4),
        downsample(512, 4)
    ]

    last_layer = Conv2D(1, 4, strides=1, padding='same')

    for block in block_stack:
        x = block(x)

    x = last_layer(x)

    return Model(inputs=[inp, target], outputs=x)


discriminator = Discriminator()
tf.keras.utils.plot_model(discriminator, show_shapes=True, dpi=64)

loss_object = tf.keras.losses.BinaryCrossentropy(from_logits=True)
LAMBDA = 100


def generator_loss(disc_generated_output, gen_output, target):
    gan_loss = loss_object(tf.ones_like(disc_generated_output), disc_generated_output)
    l1_loss = tf.reduce_mean(tf.abs(target - gen_output))

    return gan_loss + (LAMBDA * l1_loss)


def discriminator_loss(disc_real_output, disc_generated_output):
    real_loss = loss_object(tf.ones_like(disc_real_output), disc_real_output)

    generated_loss = loss_object(tf.zeros_like(disc_generated_output), disc_generated_output)

    return real_loss + generated_loss


generator_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)
discriminator_optimizer = tf.keras.optimizers.Adam(2e-4, beta_1=0.5)


def generate_images(model, test_input, target):
    prediction = model(test_input, training=True)
    plt.figure(figsize=(16, 16))

    # rearrange value of each image from [-1,1] to [0,1]
    # y = x/127.5 - 1 -> this is the formula to normalize image from [0, 255] to [-1,1]
    # x = (y + 1)*127.5 -> this return the normalized value from [-1, 1] to [0, 255]
    # x = 0.5y + 0.5 -> divide by 255 to normalize it into [0, 1]

    plt.subplot(1, 3, 1)
    plt.title("Sketch Image")
    plt.imshow(test_input[0] * 0.5 + 0.5)
    plt.axis('off')

    plt.subplot(1, 3, 2)
    plt.title("Target Image")
    plt.imshow(target[0] * 0.5 + 0.5)
    plt.axis('off')

    plt.subplot(1, 3, 3)
    plt.title("Predicted Image")
    plt.imshow(prediction[0] * 0.5 + 0.5)
    plt.axis('off')

    plt.show()


EPOCHS = 30


@tf.function
def train_step(sketch_image, ground_truth, epoch):
    with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
        generator_output = generator(sketch_image, training=True)

        disc_real_output = discriminator([sketch_image, ground_truth], training=True)
        disc_generated_output = discriminator([sketch_image, generator_output], training=True)

        gen_loss = generator_loss(disc_generated_output, generator_output, ground_truth)
        disc_loss = discriminator_loss(disc_real_output, disc_generated_output)

    generator_gradients = gen_tape.gradient(gen_loss, generator.trainable_variables)
    discriminator_gradients = disc_tape.gradient(disc_loss, discriminator.trainable_variables)

    generator_optimizer.apply_gradients(zip(generator_gradients, generator.trainable_variables))
    discriminator_optimizer.apply_gradients(zip(discriminator_gradients, discriminator.trainable_variables))
    return gen_loss, disc_loss


epoch_loss_avg_gen = tf.keras.metrics.Mean('g_loss')
epoch_loss_avg_disc = tf.keras.metrics.Mean('d_loss')

generator_mean_losses = []
discriminator_mean_losses = []


def fit(train_ds, epochs, test_ds):
    for epoch in range(1, epochs + 1):
        for example_input, example_target in test_ds.take(1):
            generate_images(generator, example_input, example_target)
        print("Epoch: ", epoch)

        for n, (sketch_image, colored_image) in tqdm(train_ds.enumerate()):
            g_loss, d_loss = train_step(sketch_image, colored_image, epoch)
            epoch_loss_avg_gen(g_loss)
            epoch_loss_avg_disc(d_loss)

        print()
        print("Generator Loss: %.2f" % epoch_loss_avg_gen.result().numpy())
        print("Discriminator Loss: %.2f" % epoch_loss_avg_disc.result().numpy())
        print("=====================================================")

        generator_mean_losses.append(epoch_loss_avg_gen.result().numpy())
        discriminator_mean_losses.append(epoch_loss_avg_disc.result().numpy())

        epoch_loss_avg_gen.reset_states()
        epoch_loss_avg_disc.reset_states()


fit(train_dataset, EPOCHS, test_dataset)

plt.plot(range(1, EPOCHS + 1), generator_mean_losses)
plt.xlabel('epochs')
plt.ylabel('loss')
plt.title('Generator Loss Plot')
plt.show()

plt.plot(range(1, EPOCHS + 1), discriminator_mean_losses)
plt.xlabel('epochs')
plt.ylabel('loss')
plt.title('Discriminator Loss Plot')
plt.show()

for n, data in enumerate(test_dataset):
    if (n > 35 and n < 40):
        sketch_image = data[0]
        ground_truth = data[1]
        generate_images(generator, sketch_image, ground_truth)
    elif (n > 40):
        break

generator.save('pix2pix_generator.h5')
discriminator.save('pix2pix_discriminator.h5')

generator.compile(optimizer='adam', loss='mean_squared_error', metrics=['accuracy'])
discriminator.compile(optimizer='adam', loss='mean_squared_error', metrics=['accuracy'])

generator.save('pix2pix_generator.h5')
discriminator.save('pix2pix_discriminator.h5')