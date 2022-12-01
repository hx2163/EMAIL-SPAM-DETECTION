import json
import os
import io
import boto3
import email
import string
import sys
import numpy as np
from hashlib import md5


ENDPOINT = 'sms-spam-classifier-mxnet-2022-12-01-00-28-46-571'


if sys.version_info < (3,):
    maketrans = string.maketrans
else:
    maketrans = str.maketrans
    
def vectorize_sequences(sequences, vocabulary_length):
    results = np.zeros((len(sequences), vocabulary_length))
    for i, sequence in enumerate(sequences):
       results[i, sequence] = 1. 
    return results

def one_hot_encode(messages, vocabulary_length):
    data = []
    for msg in messages:
        temp = one_hot(msg, vocabulary_length)
        data.append(temp)
    return data

def text_to_word_sequence(text,
                          filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',
                          lower=True, split=" "):
    """Converts a text to a sequence of words (or tokens).
    # Arguments
        text: Input text (string).
        filters: list (or concatenation) of characters to filter out, such as
            punctuation. Default: `!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n`,
            includes basic punctuation, tabs, and newlines.
        lower: boolean. Whether to convert the input to lowercase.
        split: str. Separator for word splitting.
    # Returns
        A list of words (or tokens).
    """
    if lower:
        text = text.lower()

    if sys.version_info < (3,):
        if isinstance(text, unicode):
            translate_map = dict((ord(c), unicode(split)) for c in filters)
            text = text.translate(translate_map)
        elif len(split) == 1:
            translate_map = maketrans(filters, split * len(filters))
            text = text.translate(translate_map)
        else:
            for c in filters:
                text = text.replace(c, split)
    else:
        translate_dict = dict((c, split) for c in filters)
        translate_map = maketrans(translate_dict)
        text = text.translate(translate_map)

    seq = text.split(split)
    return [i for i in seq if i]

def one_hot(text, n,
            filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',
            lower=True,
            split=' '):
    """One-hot encodes a text into a list of word indexes of size n.
    This is a wrapper to the `hashing_trick` function using `hash` as the
    hashing function; unicity of word to index mapping non-guaranteed.
    # Arguments
        text: Input text (string).
        n: int. Size of vocabulary.
        filters: list (or concatenation) of characters to filter out, such as
            punctuation. Default: `!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n`,
            includes basic punctuation, tabs, and newlines.
        lower: boolean. Whether to set the text to lowercase.
        split: str. Separator for word splitting.
    # Returns
        List of integers in [1, n]. Each integer encodes a word
        (unicity non-guaranteed).
    """
    return hashing_trick(text, n,
                         hash_function='md5',
                         filters=filters,
                         lower=lower,
                         split=split)


def hashing_trick(text, n,
                  hash_function=None,
                  filters='!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n',
                  lower=True,
                  split=' '):
    """Converts a text to a sequence of indexes in a fixed-size hashing space.
    # Arguments
        text: Input text (string).
        n: Dimension of the hashing space.
        hash_function: defaults to python `hash` function, can be 'md5' or
            any function that takes in input a string and returns a int.
            Note that 'hash' is not a stable hashing function, so
            it is not consistent across different runs, while 'md5'
            is a stable hashing function.
        filters: list (or concatenation) of characters to filter out, such as
            punctuation. Default: `!"#$%&()*+,-./:;<=>?@[\\]^_`{|}~\t\n`,
            includes basic punctuation, tabs, and newlines.
        lower: boolean. Whether to set the text to lowercase.
        split: str. Separator for word splitting.
    # Returns
        A list of integer word indices (unicity non-guaranteed).
    `0` is a reserved index that won't be assigned to any word.
    Two or more words may be assigned to the same index, due to possible
    collisions by the hashing function.
    The [probability](
        https://en.wikipedia.org/wiki/Birthday_problem#Probability_table)
    of a collision is in relation to the dimension of the hashing space and
    the number of distinct objects.
    """
    if hash_function is None:
        hash_function = hash
    elif hash_function == 'md5':
        hash_function = lambda w: int(md5(w.encode()).hexdigest(), 16)

    seq = text_to_word_sequence(text,
                                filters=filters,
                                lower=lower,
                                split=split)
    return [int(hash_function(w) % (n - 1) + 1) for w in seq]

runtime = boto3.Session().client(service_name='sagemaker-runtime',region_name='us-east-1')
SENDER = "hw3@hx2163.info"

def reply(receive_date, subject, body, score, label, recipientEmailAddress):
    client = boto3.client('ses')
    SUBJECT = "Email Spam Detection"
    BODY_TEXT = ("This email was sent with Amazon SES using the AWS SDK for Python (Boto).")
    BODY_HTML = """<html>
                    <head></head>
                    <body>
                      <p>
                        """+"We received your email sent at {} with the subject {}.<br><br> \
                        Here is a 240 character sample of the email body: <br>{}. <br><br> \
                        The email was categorized as {} with a {}% confidence."\
                        .format(receive_date, subject, body, label, score)+"""
                      </p>
                    </body>
                    </html>
                """
    CHARSET = "UTF-8"
    message = "We received your email sent at {} with the subject <i>{}<i/>. Here is a 240 character sample of the email body:\
    <b>{}</b>. The email was categorized as {} with a {} score.".format(receive_date, subject, body, label, score)

    response = client.send_email(
        Destination={
            'ToAddresses': [
                recipientEmailAddress
            ],
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': CHARSET,
                    'Data': BODY_HTML,
                },
                'Text': {
                    'Charset': CHARSET,
                    'Data': message,
                },
            },
            'Subject': {
                'Charset': CHARSET,
                'Data': SUBJECT,
            },
        },
        Source=SENDER)
    print(response)
    
def lambda_handler(event, context):
    print("This is running")
    print(event)
    print("record 0: " ,event['Records'][0])

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    s3 = boto3.resource('s3')
    obj = s3.Object(bucket ,key)
    
    print("bucket: ",bucket)
    print("obj: ",obj)
    print("key: ",key)
    
    msg = email.message_from_bytes(obj.get()['Body'].read())
    recipientEmailAddress = msg['From']
    receive_date = msg['date']
    subject = msg['subject']
    
    if msg.is_multipart():
        for part in msg.get_payload():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload()
    else:
        body = msg.get_payload()
    body = [body.strip()]
    print(recipientEmailAddress, receive_date, subject, "\n", body)
    
    vocabulary_length = 9013
    one_hot_test_messages = one_hot_encode(body, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    payload = json.dumps(encoded_test_messages.tolist())
    result = runtime.invoke_endpoint(EndpointName=ENDPOINT,ContentType='application/json',Body=payload)
    print(result["Body"])

    response = json.loads(result["Body"].read().decode("utf-8"))
    print(response)

    if response['predicted_label'][0][0] == 0:
        label = 'Not Spam'
    else:
        label = 'Spam'
    score = round(response['predicted_probability'][0][0], 4)
    score = score*100

    print(score)
    body =  body[0]
    reply(receive_date, subject, body, score,label, recipientEmailAddress)
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
