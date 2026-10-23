#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BaostockDataSource完整功能测试脚本
"""

import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = current_dir
sys.path.append(project_dir)

from src.baostock_data_source import BaostockDataSource
from src.data_source_interface import NoDataFoundError, DataSourceError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CompleteBaostockDataSourceTester:
    """BaostockDataSource完整功能测试类"""
    
    def __init__(self):
        """初始化测试器"""
        self.data_source = BaostockDataSource()
        self.test_stock_code = "sh.603871"  # 嘉友国际物流股份有限公司
        self.test_year = "2023"
        self.test_quarter = 4
        self.test_start_date = "2023-01-01"
        self.test_end_date = "2023-12-31"
        self.test_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.no_data_count = 0
        
    def test_function(self, func_name: str, test_func, *args, **kwargs):
        """通用测试函数"""
        self.test_count += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.test_count}: {func_name}")
        print(f"{'='*60}")
        
        try:
            result = test_func(*args, **kwargs)
            print(f"✅ {func_name} 测试成功！")
            print(f"   数据条数：{len(result)}")
            print(f"   数据列：{list(result.columns)}")
            
            if len(result) > 0:
                print(f"   数据预览（前3条）：")
                print(result.head(3).to_string(index=False))
            else:
                print("   数据为空")
                
            self.success_count += 1
            return True
            
        except NoDataFoundError as e:
            print(f"⚠️ {func_name} 无数据：{e}")
            self.no_data_count += 1
            return True
        except Exception as e:
            print(f"❌ {func_name} 测试失败：{e}")
            self.fail_count += 1
            return False
            
        except NoDataFoundError as e:
            print(f"⚠️ {func_name} 无数据：{e}")
            self.no_data_count += 1
            return True
        except Exception as e:
            print(f"❌ {func_name} 测试失败：{e}")
            self.fail_count += 1
            return False
    
    # ==================== 股票数据功能测试 ====================
    
    def test_1_get_historical_k_data(self):
        """测试1：K线数据获取"""
        return self.test_function(
            "get_historical_k_data",
            self.data_source.get_historical_k_data,
            code=self.test_stock_code,
            start_date="2023-12-01",
            end_date="2023-12-31",
            frequency="d",
            adjust_flag="3"
        )
    
    def test_2_get_stock_basic_info(self):
        """测试2：股票基本信息"""
        return self.test_function(
            "get_stock_basic_info",
            self.data_source.get_stock_basic_info,
            code=self.test_stock_code
        )
    
    def test_3_get_dividend_data(self):
        """测试3：分红数据"""
        return self.test_function(
            "get_dividend_data",
            self.data_source.get_dividend_data,
            code=self.test_stock_code,
            year=self.test_year,
            year_type="report"
        )
    
    def test_4_get_adjust_factor_data(self):
        """测试4：复权因子数据"""
        return self.test_function(
            "get_adjust_factor_data",
            self.data_source.get_adjust_factor_data,
            code=self.test_stock_code,
            start_date=self.test_start_date,
            end_date=self.test_end_date
        )
    
    # ==================== 财务数据功能测试 ====================
    
    def test_5_get_profit_data(self):
        """测试5：盈利能力数据"""
        return self.test_function(
            "get_profit_data",
            self.data_source.get_profit_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    def test_6_get_operation_data(self):
        """测试6：运营能力数据"""
        return self.test_function(
            "get_operation_data",
            self.data_source.get_operation_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    def test_7_get_growth_data(self):
        """测试7：成长能力数据"""
        return self.test_function(
            "get_growth_data",
            self.data_source.get_growth_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    def test_8_get_balance_data(self):
        """测试8：偿债能力数据"""
        return self.test_function(
            "get_balance_data",
            self.data_source.get_balance_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    def test_9_get_cash_flow_data(self):
        """测试9：现金流数据"""
        return self.test_function(
            "get_cash_flow_data",
            self.data_source.get_cash_flow_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    def test_10_get_dupont_data(self):
        """测试10：杜邦分析数据"""
        return self.test_function(
            "get_dupont_data",
            self.data_source.get_dupont_data,
            code=self.test_stock_code,
            year=self.test_year,
            quarter=self.test_quarter
        )
    
    # ==================== 业绩报告功能测试 ====================
    
    def test_11_get_performance_express_report(self):
        """测试11：业绩快报数据"""
        return self.test_function(
            "query_performance_express_report",
            self.data_source.get_performance_express_report,
            code="sh.600000",
            start_date="2015-01-01",
            end_date="2015-12-31"
        )
    
    def test_12_get_forecast_report(self):
        """测试12：业绩预告数据"""
        return self.test_function(
            "get_forecast_report",
            self.data_source.get_forecast_report,
            code=self.test_stock_code,
            start_date=self.test_start_date,
            end_date=self.test_end_date
        )
    
    # ==================== 市场数据功能测试 ====================
    
    def test_13_get_stock_industry(self):
        """测试13：行业分类数据"""
        return self.test_function(
            "get_stock_industry",
            self.data_source.get_stock_industry,
            code=self.test_stock_code
        )
    
    def test_14_get_sz50_stocks(self):
        """测试14：上证50成分股"""
        return self.test_function(
            "get_sz50_stocks",
            self.data_source.get_sz50_stocks
        )
    
    def test_15_get_hs300_stocks(self):
        """测试15：沪深300成分股"""
        return self.test_function(
            "get_hs300_stocks",
            self.data_source.get_hs300_stocks
        )
    
    def test_16_get_zz500_stocks(self):
        """测试16：中证500成分股"""
        return self.test_function(
            "get_zz500_stocks",
            self.data_source.get_zz500_stocks
        )
    
    def test_17_get_trade_dates(self):
        """测试17：交易日历数据"""
        return self.test_function(
            "get_trade_dates",
            self.data_source.get_trade_dates,
            start_date="2023-01-01",
            end_date="2023-01-31"
        )
    
    def test_18_get_all_stock(self):
        """测试18：全市场股票列表"""
        return self.test_function(
            "query_all_stock",
            self.data_source.get_all_stock,
            "2017-06-30"
        )
    
    # ==================== 宏观经济数据功能测试 ====================
    
    def test_19_get_deposit_rate_data(self):
        """测试19：存款利率数据"""
        return self.test_function(
            "query_deposit_rate_data",
            self.data_source.get_deposit_rate_data,
            start_date="2015-01-01",
            end_date="2015-12-31"
        )
    
    def test_20_get_loan_rate_data(self):
        """测试20：贷款利率数据"""
        return self.test_function(
            "query_loan_rate_data",
            self.data_source.get_loan_rate_data,
            start_date="2015-01-01",
            end_date="2015-12-31"
        )
    
    def test_21_get_required_reserve_ratio_data(self):
        """测试21：存款准备金率数据"""
        return self.test_function(
            "query_required_reserve_ratio_data",
            self.data_source.get_required_reserve_ratio_data,
            start_date="2015-01-01",
            end_date="2015-12-31"
        )
    
    def test_22_get_money_supply_data_month(self):
        """测试22：月度货币供应量数据（修复后）"""
        return self.test_function(
            "get_money_supply_data_month",
            self.data_source.get_money_supply_data_month,
            start_date="2023-01",
            end_date="2023-12"
        )
    
    def test_23_get_money_supply_data_year(self):
        """测试23：年度货币供应量数据（修复后）"""
        return self.test_function(
            "get_money_supply_data_year",
            self.data_source.get_money_supply_data_year,
            start_date="2023",
            end_date="2023"
        )
    
    # def test_24_get_shibor_data(self):
    #     """测试24：SHIBOR数据（检查支持）"""
    #     return self.test_function(
    #         "get_shibor_data",
    #         self.data_source.get_shibor_data,
    #         start_date="2023-01-01",
    #         end_date="2023-12-31"
    #     )
    
    # ==================== 新闻爬虫功能测试 ====================
    
    def test_25_crawl_news(self):
        """测试25：新闻爬虫功能"""
        print(f"\n{'='*60}")
        print(f"测试 {self.test_count + 1}: crawl_news")
        print(f"{'='*60}")
        
        test_queries = [
            "嘉友国际",
        ]
        
        success_count = 0
        total_count = len(test_queries)
        
        for query in test_queries:
            print(f"测试查询: '{query}'")
            print("-" * 50)
            
            try:
                result = self.data_source.crawl_news(query, 3)
                print("✅ 爬取新闻成功！")
                print(f"   查询: {query}")
                print(f"   结果: {result}")
                success_count += 1
                
            except Exception as e:
                print(f"❌ 爬取新闻失败: {e}")
            
            print("\n" + "=" * 60 + "\n")
        
        self.test_count += 1
        if success_count == total_count:
            self.success_count += 1
            print(f"✅ crawl_news 测试成功！({success_count}/{total_count})")
        else:
            self.fail_count += 1
            print(f"❌ crawl_news 测试失败！({success_count}/{total_count})")
        
        return success_count == total_count
    
    
    # ==================== 运行所有测试 ====================
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始测试BaostockDataSource所有功能")
        print(f"📊 测试股票：{self.test_stock_code} (嘉友国际物流股份有限公司)")
        print(f"📅 测试时间范围：{self.test_start_date} 到 {self.test_end_date}")
        print(f"📈 测试年份：{self.test_year}年Q{self.test_quarter}")
        
        # 运行所有测试
        tests = [
            # 股票数据功能
            self.test_1_get_historical_k_data,
            self.test_2_get_stock_basic_info,
            self.test_3_get_dividend_data,
            self.test_4_get_adjust_factor_data,
            
            # 财务数据功能
            self.test_5_get_profit_data,
            self.test_6_get_operation_data,
            self.test_7_get_growth_data,
            self.test_8_get_balance_data,
            self.test_9_get_cash_flow_data,
            self.test_10_get_dupont_data,
            
            # 业绩报告功能
            self.test_11_get_performance_express_report,
            self.test_12_get_forecast_report,
            
            # 市场数据功能
            self.test_13_get_stock_industry,
            self.test_14_get_sz50_stocks,
            self.test_15_get_hs300_stocks,
            self.test_16_get_zz500_stocks,
            self.test_17_get_trade_dates,
            self.test_18_get_all_stock,
            
            # 宏观经济数据功能
            self.test_19_get_deposit_rate_data,
            self.test_20_get_loan_rate_data,
            self.test_21_get_required_reserve_ratio_data,
            self.test_22_get_money_supply_data_month,
            self.test_23_get_money_supply_data_year,
            # self.test_24_get_shibor_data,
            
            # 新闻爬虫功能
            self.test_25_crawl_news,
        ]
        
        for test in tests:
            test()
        
        # 输出测试结果统计
        print("\n" + "="*60)
        print("📊 完整测试结果统计")
        print("="*60)
        print(f"总测试数：{self.test_count}")
        print(f"成功数：{self.success_count}")
        print(f"无数据数：{self.no_data_count}")
        print(f"失败数：{self.fail_count}")
        print(f"成功率：{(self.success_count + self.no_data_count)/self.test_count*100:.1f}%")
        
        # 详细分类统计
        print(f"\n📈 详细分类：")
        print(f"   ✅ 功能正常：{self.success_count}个")
        print(f"   ⚠️ 无数据：{self.no_data_count}个")
        print(f"   ❌ 功能失败：{self.fail_count}个")
    
        
        if self.fail_count == 0:
            print("\n🎉 所有功能测试通过！")
        else:
            print(f"\n⚠️ 有{self.fail_count}个功能测试失败，请检查相关功能")
        
        print("="*60)

def main():
    """主函数"""
    try:
        tester = CompleteBaostockDataSourceTester()
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误：{e}")
        logger.exception("测试过程中发生错误")

if __name__ == "__main__":
    main() 
