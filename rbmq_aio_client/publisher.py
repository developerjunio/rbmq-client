import json
import addict
import asyncio
import aio_pika
import aio_pika.abc
from structlog import get_logger
from typing import List, Union
from datetime import datetime

class Publisher:
    
    def __init__(self, config: "dict", debug=True):
        self.__config = addict.Dict(config)
        self.__debug = debug
        self.__logger = get_logger()
        self.__messages: "List[aio_pika.Message, str]" = []
    
    async def main(self, loop, connection_type: "Union[str, aio_pika.RobustConnection]", exchange: "str"):
        if isinstance(connection_type, str):
            connection_args = self.__config.connections.get(connection_type)
            connection: aio_pika.RobustConnection = await aio_pika.connect_robust(connection_args.uri, 
                                                                                loop=loop, 
                                                                                timeout=connection_args.timeout)
        elif isinstance(connection_type, aio_pika.RobustConnection):
            connection = connection_type
        else:
            raise Exception("Invalid Connection Type")   
        
        
        exchange_args = self.__config.exchanges.get(exchange)
        
        if self.__debug:
            if isinstance(connection_args, dict):
                self.__logger.debug(f"ConnectionProfile: {connection_args.uri}")
                
            for key, value in exchange_args.items():
                self.__logger.debug(f"QueueProfile: {key}={value}")
        
        connection: aio_pika.RobustConnection = await aio_pika.connect_robust(connection_args.uri, 
                                                                              loop=loop, 
                                                                              timeout=connection_args.timeout)
        self.__logger.info("Connection Established")
        
        channel: aio_pika.abc.AbstractChannel = await connection.channel()
        self.__logger.info("Channel Established")
        
        exchange: aio_pika.Exchange = await channel.declare_exchange(exchange_args.name, 
                                                                     exchange_args.type, 
                                                                     durable=exchange_args.durable,
                                                                     auto_delete=exchange_args.auto_delete,
                                                                     internal=exchange_args.internal,
                                                                     passive=exchange_args.passive,
                                                                     timeout=exchange_args.timeout)
        self.__logger.info("Exchange Declared")
        
        for index, item in enumerate(self.__messages):
            if self.__debug:
                self.__logger.debug('Message Published @ {}'.format(index))
                self.__logger.debug('Message Profile: {}'.format(item.message_id))
                
            await exchange.publish(item[0], item[1], timeout=item[2])
        
        await connection.close()
    
    def push(self, 
             routing_key: "str", 
             message_id: "str",
             payload: "str", 
             persistent: "int"=aio_pika.DeliveryMode.PERSISTENT, 
             expiration: "int"=86400,
             publish_timeout: "int"=1, 
             reply_queue: "str"=None):
        message = aio_pika.Message(body=json.dumps(payload).encode(), 
                                   delivery_mode=persistent,
                                   expiration=expiration,
                                   message_id=message_id,
                                   timestamp=datetime.utcnow().timestamp(), 
                                   reply_to=reply_queue)
        self.__messages.append([message, routing_key, publish_timeout])
        return self
    
    def run(self, connection, exchange):
        async def __run():
            try:
                loop = asyncio.get_event_loop()
                await self.main(loop, connection, exchange)
            except Exception as e:
                print(e)
        asyncio.run(__run())
    