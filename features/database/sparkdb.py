from pyspark.sql import SparkSession

### Using only local mode for testing, in production you would connect to a cluster
spark = SparkSession \
    .builder \
    .appName("Python Spark SQL basic example") \
    .master("local[*]")\
    .config("spark.driver.host", "127.0.0.1")\
    .config("spark.driver.bindAddress", "127.0.0.1")\
    .getOrCreate()

df = spark.read.json("data/efrag_pdf_links.json", multiLine=True)

### Create a DataFrame containing the employees data
df = spark.createDataFrame(df)
df.show()